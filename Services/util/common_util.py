import re
import time
from os import remove, getcwd
from os.path import exists
from typing import Union

import markdown2
from httpx import AsyncClient
from loguru import logger
from lxml import html
from lxml.html.clean import Cleaner
from nonebot import CommandSession
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from Services.util.ctx_utility import get_user_id, get_group_id


def chunk_string(string, length):
    return (string[0 + i:length + i] for i in range(0, len(string), length))


def _compile_forward_node(self_id: str, data: str):
    return {
        'type': 'node',
        'data': {
            'name': '月朗风清',
            'uin': self_id,
            'content': data
        }
    }


async def get_general_ctx_info(ctx: dict) -> (int, int, int):
    message_id = ctx['message_id']
    return message_id, get_user_id(ctx), get_group_id(ctx)


async def time_to_literal(time_string: int) -> str:
    hour = time_string // 3600
    time_string %= 3600

    minute = time_string // 60
    second = time_string % 60

    result = ''
    result += f'{hour}时' if hour > 0 else ''
    result += f'{minute}分' if minute > 0 else ''
    result += f'{second}秒'

    return result


def compile_forward_message(self_id: Union[int, str], *args: str) -> list:
    self_id = str(self_id)
    data_list = []
    for arg in args:
        data_list.append(_compile_forward_node(self_id, arg.strip()))

    return data_list


def is_float(content: str) -> bool:
    try:
        float(content)
        return True

    except ValueError:
        return False


async def check_if_number_user_id(session: CommandSession, arg: str):
    if not arg.isdigit():
        session.finish('输入非法')

    return arg


def markdown_to_html(string: str):
    string = string.replace('```c#', '```').replace('&#91;', '[').replace('&#93;', ']')
    is_html = html.fromstring(string).find('.//*') is not None
    if is_html:
        cleaner = Cleaner()
        cleaner.javascript = True
        cleaner.style = True

        string = cleaner.clean_html(string)

        logger.info(f'Cleaned string: {string}')

    html_string = markdown2.markdown(string, extras=['fenced-code-blocks', 'strike', 'tables', 'task_list'])
    html_string_with_latex = re.findall(r'\${1,2}.*?<em>.*?\${1,2}', html_string)
    if html_string_with_latex:
        for latex in html_string_with_latex:
            html_string = html_string.replace(latex, latex.replace('</em>', '').replace('<em>', '_'))

    file_name = f'{getcwd()}/data/bot/response/{int(time.time())}.html'
    with open(file_name, 'w+', encoding='utf-8') as file:
        file.write(r"""
<script type="text/x-mathjax-config">
    MathJax.Hub.Config({
        extensions: ["tex2jax.js", "AMSmath.js"],
        jax: ["input/TeX", "output/HTML-CSS"],
        tex2jax: {
            inlineMath: [ ['$','$'] ],
            displayMath: [ ['$$','$$'] ],
            processEscapes: true
        },
    });
</script>
<script type="text/javascript" src="https://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML">
</script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/styles/default.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@3.4.1/dist/css/bootstrap.min.css"
 integrity="sha384-HSMxcRTRxnN+Bdg0JdbxYKrThecOKuH5zCYotlSAcp1+c8xmyTe9GYg1l9a69psu" crossorigin="anonymous">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/highlight.min.js"></script>

""" + f'<body><div class="container">{html_string}</div></body>')

    return file_name


def html_to_image(file_name):
    file_name_png = f'{getcwd()}/data/bot/response/{int(time.time())}.png'
    options = Options()
    options.add_argument('--headless')
    options.add_argument("--force-device-scale-factor=3.0")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(5)
    driver.get(f'file:///{file_name}')
    driver.execute_script("hljs.highlightAll();")

    try:
        WebDriverWait(driver, 15, poll_frequency=0.5) \
            .until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='MathJax_Message'][contains(@style, 'display: none')]")))
    except TimeoutException:
        logger.warning('Render markdown exceeded time limit.')
    finally:
        required_width = driver.execute_script('return document.body.parentNode.scrollWidth')
        required_height = driver.execute_script('return document.body.parentNode.scrollHeight')

        element = driver.find_element(by=By.CLASS_NAME, value='container')
        driver.set_window_size(required_width, required_height + 2000)
        element.screenshot(file_name_png)

        driver.quit()

        remove(file_name)

        return file_name_png


def markdown_to_image(text: str) -> (str, bool):
    try:
        html_file = markdown_to_html(text)
        return html_to_image(html_file), True
    except Exception as err:
        logger.error(f'Markdown render failed {err.__class__}')
        return '渲染出错力', False


class HttpxHelperClient:
    def __init__(self):
        self.headers = {
            'User-Agent': 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/84.0.4147.125 Safari/537.36'
        }

    async def get(self, url: str, timeout=5.0, headers=None):
        headers = headers if headers is not None else self.headers

        async with AsyncClient(timeout=timeout, headers=headers, verify=False) as client:
            return await client.get(url)

    async def post(self, url: str, json: dict, headers=None, timeout=10.0):
        headers = headers if headers is not None else self.headers
        async with AsyncClient(headers=headers, timeout=timeout, default_encoding='utf-8') as client:
            return await client.post(url, json=json)

    async def download(self, url: str, file_name: str, timeout=20.0, headers=None):
        file_name = file_name.replace('\\', '/')
        headers = headers if headers is not None else self.headers

        try:
            if not exists(file_name):
                with open(file_name, 'wb') as file:
                    async with AsyncClient(timeout=timeout, headers=headers) as client:
                        async with client.stream('GET', url) as response:
                            async for chunk in response.aiter_bytes():
                                file.write(chunk)

            return file_name
        except Exception as err:
            logger.warning(f'Download failed in common util download: {err.__class__}')

        return ''
