import json
import os
import random
import re
import shutil
import time

import aiocqhttp.event
import nonebot
import pixivpy3
import requests
from aiocqhttp import MessageSegment
from nonebot.message import CanceledException
from nonebot.plugin import PluginManager

import config
from Shadiao import WaifuFinder, ark_nights, Shadiao, pcr_news
from awesome.adminControl import permission as perm
from awesome.adminControl import shadiaoAdmin, setuSanity
from awesome.adminControl import userControl


class arknightsPity:
    def __init__(self):
        self.sanityPollDict = {}

    def recordPoll(self, group_id):
        if group_id not in self.sanityPollDict:
            self.sanityPollDict[group_id] = 10
        else:
            self.sanityPollDict[group_id] += 10

    def getOffsetSetting(self, group_id) -> int:
        if group_id not in self.sanityPollDict:
            self.recordPoll(group_id)
            return 0
        else:
            pollCount = self.sanityPollDict[group_id]
            if pollCount <= 50:
                return 0
            else:
                return (pollCount - 50) * 2

    def resetOffset(self, group_id):
        self.sanityPollDict[group_id] = 0


pcr_api = pcr_news.GetPCRNews()
sanity_meter = setuSanity.SetuSanity()
aapi = pixivpy3.AppPixivAPI()
api = ark_nights.ArkHeadhunt(times=10)
admin_control = shadiaoAdmin.Shadiaoadmin()
user_control_module = userControl.UserControl()
ark_pool_pity = arknightsPity()


get_privilege = lambda x, y : user_control_module.get_user_privilege(x, y)

if not os.path.exists("E:/pixivPic/"):
    os.makedirs("E:/pixivPic/")

@nonebot.message_preprocessor
async def message_preprocessing(unused1: nonebot.NoneBot, event: aiocqhttp.event, unused2: PluginManager):
    group_id = event.group_id
    if group_id is not None:
        if not admin_control.get_data(group_id, 'enabled') \
        and not get_privilege(event['user_id'], perm.OWNER):
            raise CanceledException('Group disabled')


@nonebot.on_command('来个老婆', aliases=('来张waifu', '来个waifu', '老婆来一个'), only_to_me=False)
async def sendWaifu(session: nonebot.CommandSession):
    waifuAPI = WaifuFinder.waifuFinder()
    path, message = waifuAPI.getImage()
    if not path:
        await session.send(message)
    else:
        nonebot.logger.info('Get waifu pic: %s' % path)
        await session.send('[CQ:image,file=file:///%s]\n%s' % (path, message))


@nonebot.on_command('shadiao', aliases=('沙雕图', '来一张沙雕图', '机器人来张沙雕图'), only_to_me=False)
async def shadiaoSend(session: nonebot.CommandSession):
    shadiao = Shadiao.ShadiaoAPI()
    file = shadiao.get_picture()
    await session.send('[CQ:image,file=file:///%s]' % file)

@nonebot.on_command('PCR', only_to_me=False)
async def PCRNewsSend(session : nonebot.CommandSession):
    try:
        await session.send(await pcr_api.get_content())
    except Exception as e:
        await session.send('%s' % e)

@nonebot.on_command('你群有多色', only_to_me=False)
async def getSetuStat(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish('本功能是群组功能')

    times, rank, yanche, delta, arkStat, arkPull = sanity_meter.get_usage(ctx['group_id'])
    setuNotice = f'自统计功能实装以来，你组查了{times}次色图！' \
                 f'{"位居色图查询排行榜的第" + str(rank) + "！" if rank != -1 else ""}\n' \
                 f'距离第{2 if rank == 1 else rank - 1}位相差{delta}次搜索！\n'

    yancheNotice = ('并且验车了' + str(yanche) + "次！\n") if yanche > 0 else ''
    arkData = ''
    if arkStat:
        arkData += f'十连充卡共{arkPull}次，理论消耗合成玉{arkPull * 6000}。抽到了：\n' \
                   f"3星{arkStat['3']}个，4星{arkStat['4']}个，5星{arkStat['5']}个，6星{arkStat['6']}个"

    await session.send(setuNotice + yancheNotice + arkData)

@nonebot.on_command('理智查询', only_to_me=False)
async def sanityChecker(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' in ctx:
        idNum = ctx['group_id']
    else:
        idNum = ctx['user_id']

    if idNum in sanity_meter.get_sanity_dict():
        sanity = sanity_meter.get_sanity(idNum)
    else:
        sanity = sanity_meter.get_max_sanity()
        sanity_meter.set_sanity(idNum, sanity_meter.get_max_sanity())

    await session.send('您的剩余理智为：%d' % sanity)

@nonebot.on_command('理智补充', only_to_me=False)
async def sanityRefill(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.ADMIN):
        await session.finish('您没有权限补充理智')
        return

    try:
        idNum = int(session.get('idNum', prompt='请输入要补充的ID'))
        sanityAdd = int(session.get('sanityAdd', prompt='那要补充多少理智呢？'))
    except ValueError:
        await session.finish('未找到能够补充的对象')
        return

    try:
        sanity_meter.fill_sanity(idNum, sanity=sanityAdd)
    except KeyError:
        await session.finish('未找到能够补充的对象')

    await session.finish('补充理智成功！')

@nonebot.on_command('happy', aliases={'快乐时光'}, only_to_me=False)
async def startHappyHours(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = str(ctx['user_id'])
    if get_privilege(id_num, perm.OWNER):
        if sanity_meter.happy_hours:
            sanity_meter.happy_hours = False
            await session.finish('已设置关闭快乐时光')

        sanity_meter.happy_hours = not sanity_meter.happy_hours
        await session.finish('已设置打开快乐时光')

    else:
        await session.finish('您无权使用本指令')

@nonebot.on_command('设置R18', only_to_me=False)
async def SetR18(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.WHITELIST):
        await session.finish('您无权进行该操作')

    if 'group_id' in ctx:
        id_num = ctx['group_id']
    else:
        await session.finish('请在需要禁用或开启R18的群内使用本指令')
        id_num = -1

    setting = session.get('stats', prompt='请设置开启或关闭')
    if '开' in setting:
        admin_control.set_data(id_num, 'R18', True)
        resp = '开启'
    else:
        admin_control.set_data(id_num, 'R18', False)
        resp = '关闭'

    await session.finish('Done! 已设置%s' % resp)

@nonebot.on_command('掉落查询', only_to_me=False)
async def checkPCRDrop(session : nonebot.CommandSession):
    query = session.get('group_id', prompt='请输入要查询的道具名称')
    response = await pcr_api.pcr_check(query=query)
    await session.finish(response)

@nonebot.on_command('方舟十连', only_to_me=False)
async def tenPolls(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.send('这是群组功能')
        return

    if get_privilege(ctx['user_id'], perm.OWNER):
        api.get_randomized_results(98)

    else:
        offset = ark_pool_pity.getOffsetSetting(ctx['group_id'])
        api.get_randomized_results(offset)
        classList = api.random_class
        six_star_count = classList.count(6)
        if 6 in classList:
            ark_pool_pity.resetOffset(ctx['group_id'])

        five_star_count = classList.count(5)

        data = {
            "6" : six_star_count,
            "5" : five_star_count,
            "4" : classList.count(4),
            "3" : classList.count(3)
        }

        if six_star_count == 0 and five_star_count == 0:
            sanity_meter.set_user_data(ctx['user_id'], 'only_four_three')

        sanity_meter.set_usage(group_id=ctx['group_id'], tag='pulls', data=data)
        sanity_meter.set_usage(group_id=ctx['group_id'], tag='pull')
        sanity_meter.set_user_data(ctx['user_id'], 'six_star_pull', six_star_count)

    qqNum = ctx['user_id']
    await session.send('[CQ:at,qq=%d]\n%s' % (qqNum, api.__str__()))

@nonebot.on_command('统计', only_to_me=False)
async def statPlayer(session: nonebot.CommandSession):
    get_stat = lambda key, lis : lis[key] if key in lis else 0
    ctx = session.ctx.copy()
    user_id = ctx['user_id']
    statDict = sanity_meter.get_user_data(user_id)
    if not statDict:
        await session.send(f'[CQ:at,qq={user_id}]还没有数据哦~')
    else:
        poker_win = get_stat('poker', statDict)
        six_star_pull = get_stat('six_star_pull', statDict)
        yanche = get_stat('yanche', statDict)
        setu = get_stat('setu', statDict)
        question = get_stat('question', statDict)
        unlucky = get_stat('only_four_three', statDict)
        same = get_stat('hit_xp', statDict)
        zc = get_stat('zc', statDict)
        chp = get_stat('chp', statDict)
        roulette = get_stat('roulette', statDict)
        horse_race = get_stat('horse_race', statDict)

        await session.send(     f'用户[CQ:at,qq={user_id}]：\n' +
                               (f'比大小赢得{poker_win}次\n' if poker_win != 0 else '') +
                               (f'方舟抽卡共抽到{six_star_pull}个六星干员\n' if six_star_pull != 0 else '') +
                               (f'紫气东来{unlucky}次\n' if unlucky != 0 else '') +
                               (f'验车{yanche}次\n' if yanche != 0 else '') +
                               (f'查了{setu}次的色图！\n' if setu != 0 else '') +
                               (f'问了{question}次问题\n' if question != 0 else '') +
                               (f'和bot主人 臭 味 相 投{same}次\n' if same != 0 else '') +
                               (f'嘴臭{zc}次\n' if zc != 0 else '') +
                               (f'彩虹屁{chp}次\n' if chp != 0 else '') +
                               (f'轮盘赌被处死{roulette}次\n' if roulette != 0 else '') +
                               (f'赛马获胜{horse_race}次\n' if horse_race != 0 else '')

                           )

@nonebot.on_command('统计xp', only_to_me=False)
async def get_xp_stat_data(session : nonebot.CommandSession):
    xp_stat = sanity_meter.get_xp_data()
    response = ''
    for item, keys in xp_stat.items():
        response += f'关键词：{item} --> Hit: {keys}\n'

    await session.finish(response)

@nonebot.on_command('娱乐开关', only_to_me=False)
async def pixivOff(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = str(ctx['user_id'])
    if not get_privilege(id_num, perm.WHITELIST):
        await session.finish('您无权进行该操作')

    group_id = session.get('group_id', prompt='请输入要禁用所有功能的qq群')
    if not str(group_id).isdigit():
        await session.finish('这不是qq号哦~')

    if admin_control.get_data(group_id, 'enabled'):
        admin_control.set_data(group_id, 'enabled', False)
        await session.finish('已禁用娱乐功能！')
    else:
        admin_control.set_data(group_id, 'enabled', True)
        await session.finish('已开启娱乐功能！')

@nonebot.on_command('设置色图禁用', only_to_me=False)
async def setBlackListGroup(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.WHITELIST):
        group_id = session.get('group_id', prompt='请输入要禁用的qq群')
        try:
            admin_control.set_data(group_id, 'banned', True)
        except ValueError:
            await session.finish('这不是数字啊kora')

        await session.finish('你群%s没色图了' % group_id)

@nonebot.on_command('删除色图禁用', only_to_me=False)
async def deleteBlackListGroup(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.WHITELIST):
        group_id = session.get('group_id', prompt='请输入要禁用的qq群')
        try:
            admin_control.set_data(group_id, 'banned', False)
        except ValueError:
            await session.finish('emmm没找到哦~')

        await session.finish('你群%s又有色图了' % group_id)

@setBlackListGroup.args_parser
@deleteBlackListGroup.args_parser
@checkPCRDrop.args_parser
@pixivOff.args_parser
async def _setGroupProperty(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['group_id'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('qq组号不能为空')

    session.state[session.current_key] = stripped_arg

@nonebot.on_command('闪照设置', only_to_me=False)
async def set_exempt(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.ADMIN) or 'group_id' not in ctx:
        return

    group_id = ctx['group_id']
    if admin_control.get_data(group_id, 'exempt'):
        admin_control.set_data(group_id, 'exempt', False)
        await session.finish('已打开R18闪照发送模式')

    else:
        admin_control.set_data(group_id, 'exempt', True)
        await session.finish('本群R18图将不再已闪照形式发布')

@nonebot.on_command('验车', only_to_me=False)
async def avValidator(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    key_word = session.get('key_word', prompt='在？你要让我查什么啊baka')
    validator = Shadiao.Avalidator(text=key_word)
    if 'group_id' in ctx:
        sanity_meter.set_usage(ctx['group_id'], tag='yanche')
        sanity_meter.set_user_data(ctx['user_id'], 'yanche')

    await session.finish(validator.get_content())

@nonebot.on_command('色图', aliases='来张色图', only_to_me=False)
async def pixivSend(session: nonebot.CommandSession):
    if not getStatus():
        await session.finish('机器人现在正忙，不接受本指令。')

    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    group_id = ctx['group_id'] if 'group_id' in ctx else -1
    user_id = ctx['user_id']
    if 'group_id' in ctx and not get_privilege(user_id, perm.OWNER):
        if admin_control.get_data(ctx['group_id'], 'banned'):
            await session.finish('管理员已设置禁止该群接收色图。如果确认这是错误的话，请联系bot制作者')

    sanity = -1
    monitored = False
    multiplier = 1
    doMultiply = False

    if group_id in sanity_meter.get_sanity_dict():
        sanity = sanity_meter.get_sanity(group_id)

    elif 'group_id' not in ctx and not get_privilege(user_id, perm.WHITELIST):
        await session.finish('我主人还没有添加你到信任名单哦。请找BOT制作者要私聊使用权限~')

    else:
        sanity = sanity_meter.get_max_sanity()
        sanity_meter.set_sanity(group_id=group_id, sanity=sanity_meter.get_max_sanity())

    if sanity <= 0:
        if group_id not in sanity_meter.remind_dict or not sanity_meter.remind_dict[group_id]:
            sanity_meter.set_remid_dict(group_id, True)
            await session.finish(
                '您已经理智丧失了，不能再查了哟~（小提示：指令理智查询可以帮您查看本群还剩多少理智，理智补充算法：快乐时光下：5点/2分钟（上限80）、非快乐时光下：1点/2分钟（上限40））')

    if not admin_control.get_if_authed():
        aapi.set_auth(access_token=admin_control.get_access_token(),
                      refresh_token='iL51azZw7BWWJmGysAurE3qfOsOhGW-xOZP41FPhG-s')
        admin_control.set_if_authed(True)

    is_exempt = admin_control.get_data(group_id, 'exempt') if group_id != -1 else False

    key_word = str(session.get('key_word', prompt='请输入一个关键字进行查询')).lower()

    if key_word in sanity_meter.get_bad_word_dict():
        multiplier = sanity_meter.get_bad_word_dict()[key_word]
        doMultiply = True
        if multiplier > 0:
            await session.send(f'该查询关键词在黑名单中，危机合约模式已开启：本次色图搜索将{multiplier}倍消耗理智')
        else:
            await session.send(f'该查询关键词在白名单中，支援合约已开启：本次色图搜索将{abs(multiplier)}倍补充理智')

    if key_word in sanity_meter.get_monitored_keywords():
        await session.send('该关键词在主人的监控下，本次搜索不消耗理智，且会转发主人一份√')
        monitored = True
        if 'group_id' in ctx:
            sanity_meter.set_user_data(user_id, 'hit_xp')
            sanity_meter.set_xp_data(key_word)

    if re.match(r'.*?祈.*?雨', key_word):
        if re.match(r'(屑|垃.*?圾|辣.*?鸡|笨.*?蛋).*?祈.*?雨', key_word):
            user_control_module.set_user_privilege(str(ctx['user_id']), perm.BANNED, True)
            await session.finish('恭喜您被自动加入黑名单啦！')

        await session.finish('我静观天象，发现现在这个时辰不适合发我主人的色图。')

    elif '色图' in key_word:
        await session.finish('[CQ:image,file=file:///C:/dl/others/QQ图片20191013212223.jpg]')

    elif '屑bot' in key_word:
        await session.finish('你屑你🐴呢')

    if '最新' in key_word:
        json_result = aapi.illust_ranking('week')
    else:
        json_result = aapi.search_illust(word=key_word, sort="popular_desc")

    # 看一下access token是否过期
    if 'error' in json_result:
        admin_control.set_if_authed(False)
        try:
            admin_control.set_access_token(
                access_token=aapi.auth(username=config.user_name, password=config.password).response.access_token)
            await session.send('新的P站匿名访问链接已建立……')
            admin_control.set_if_authed(True)

        except pixivpy3.PixivError:
            return

    if '{user=' in key_word:
        key_word = re.findall(r'{user=(.*?)}', key_word)
        if key_word:
            key_word = key_word[0]
        else:
            await session.finish('未找到该用户。')

        json_user = aapi.search_user(word=key_word, sort="popular_desc")
        if json_user.user_previews:
            user_id = json_user.user_previews[0].user.id
            json_result = aapi.user_illusts(user_id)
        else:
            await session.send("%s无搜索结果或图片过少……" % key_word)
            return

    else:
        json_result = aapi.search_illust(word=key_word, sort="popular_desc")

    if not json_result.illusts or len(json_result.illusts) < 4:
        nonebot.logger.warning(f"未找到图片, keyword = {key_word}")
        await session.send("%s无搜索结果或图片过少……" % key_word)
        return

    illust = random.choice(json_result.illusts)
    isR18 = illust.sanity_level == 6
    if not monitored:
        if isR18:
            sanity_meter.drain_sanity(group_id=group_id, sanity=2 if not doMultiply else 2 * multiplier)
        else:
            sanity_meter.drain_sanity(group_id=group_id, sanity=1 if not doMultiply else 1 * multiplier)

    path = download_image(illust)
    try:
        nickname = ctx['sender']['nickname']
    except TypeError:
        nickname = 'null'

    bot = nonebot.get_bot()
    if not isR18:
        try:
            await session.send(
                f'[CQ:at,qq={user_id}]\nPixiv ID: {illust.id}\n' + MessageSegment.image(f'file:///{path}')
            )

            nonebot.logger.info("sent image on path: " + path)

        except Exception as e:
            nonebot.logger.info('Something went wrong %s' % e)
            await session.send('悲，屑TX不收我图。')
            return

    elif isR18 and (group_id == -1 or admin_control.get_data(group_id, 'R18')):
        if not is_exempt:
            await session.send(MessageSegment.image(f'file:///{path}', destruct=True))
        else:
            await session.send(MessageSegment.image(f'file:///{path}'))

        await session.finish('图片我发过了哦~看不到就是TXXXXX的锅~')

    else:
        if not monitored:
            await session.send('我找到色图了！\n但是我发给我主人了_(:зゝ∠)_')
            await bot.send_private_msg(user_id=634915227,
                                       message=f"图片来自：{nickname}\n" +
                                               f'Pixiv ID: {illust.id}\n' +
                                               MessageSegment.image(f'file:///{path}')
            )


    sanity_meter.set_usage(group_id, 'setu')
    if 'group_id' in ctx:
        sanity_meter.set_user_data(user_id, 'setu')

    if monitored and not get_privilege(user_id, perm.OWNER):
        await bot.send_private_msg(user_id=634915227,
                                   message=f'图片来自：{nickname}\n'
                                           f'查询关键词:{key_word}\n'
                                           f'Pixiv ID: {illust.id}\n'
                                           '关键字在监控中' + f'[CQ:image,file=file:///{path}]')

def download_image(illust):
    if illust['meta_single_page']:
        if 'original_image_url' in illust['meta_single_page']:
            image_url = illust.meta_single_page['original_image_url']
        else:
            image_url = illust.image_urls['medium']
    else:
        image_url = illust.image_urls['medium']

    nonebot.logger.info("%s: %s, %s" % (illust.title, image_url, illust.id))
    image_file_name = image_url.split('/')[-1].replace('_', '')
    path = 'D:/go-cqhttp/data/images/' + image_file_name
    nonebot.logger.info("PATH = " + path)
    if not os.path.exists(path):
        try:
            response = aapi.requests_call('GET', image_url, headers={'Referer': 'https://app-api.pixiv.net/'}, stream=True)
            with open(path, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)

        except Exception as err:
            nonebot.logger.info(f'Download image error: {err}')

    return path

@nonebot.on_command('ghs', only_to_me=False)
async def get_random_image(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        return

    id_num = ctx['group_id']
    user_id = ctx['user_id']
    sanity_meter.set_usage(id_num, 'setu')
    sanity_meter.set_user_data(user_id, 'setu')

    await session.finish(await get_random())

async def get_random():
    headers = {
        'Authorization': 'HM9GYMGhY7ccUk7'
    }

    sfw = 'https://gallery.fluxpoint.dev/api/sfw/anime'
    nsfw = 'https://gallery.fluxpoint.dev/api/nsfw/lewd'
    rand_num = random.randint(0, 101)
    if rand_num >= 80:
        is_nsfw = True
    else:
        is_nsfw = False

    page = requests.get(nsfw if is_nsfw else sfw, headers=headers).json()

    filename = page['file'].split('/')[-1]

    image_page = requests.get(page['file'])
    path = f'D:/CQP/QPro/data/image/{filename}'
    if not os.path.exists(path):
        with open(path, 'wb') as f:
            f.write(image_page.content)

    return MessageSegment.image(f'file:///{path}') if not is_nsfw else MessageSegment.image(f'file:///{path}', destruct=True)

@pixivSend.args_parser
@avValidator.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('要查询的关键词不能为空')

    session.state[session.current_key] = stripped_arg

@nonebot.on_command('嘴臭一个', aliases=('骂我', '你再骂', '小嘴抹蜜', '嘴臭一下', '机器人骂我'), only_to_me=False)
async def zuiChou(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    if 'group_id' in ctx:
        sanity_meter.set_user_data(ctx['user_id'], 'zc')

    random.seed(time.time_ns())
    randNum = random.randint(0, 50)
    if randNum > 15:
        try:
            req = requests.get('https://nmsl.shadiao.app/api.php?level=min&from=qiyu', timeout=5)
        except requests.exceptions.Timeout:
            await session.send('骂不出来了！')
            return

        response = req.text
        await session.send(response)

    elif randNum > 10:
        try:
            req = requests.get('https://nmsl.shadiao.app/api.php?level=max&from=qiyu', timeout=5)
        except requests.exceptions.Timeout:
            await session.send('骂不出来了！')
            return

        response = req.text
        await session.send(response)

    else:
        file = os.listdir('C:\dl\zuichou')
        fileCount = len(file) - 1
        random.seed(time.time_ns())
        randNum = random.randint(0, fileCount)
        await session.send("[CQ:image,file=file:///C:\dl\zuichou\zuichou%d.jpg]" % randNum)

@nonebot.on_command('彩虹屁', aliases=('拍个马屁', '拍马屁', '舔TA'), only_to_me=False)
async def caiHongPi(session: nonebot.CommandSession):
    ctx = session.ctx.copy()

    if get_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    if 'group_id' in ctx:
        sanity_meter.set_user_data(ctx['user_id'], 'chp')

    try:
        req = requests.get('https://chp.shadiao.app/api.php?from=qiyu', timeout=5)
    except requests.exceptions.Timeout:
        await session.send('拍马蹄上了_(:зゝ∠)_')
        return


    text = req.text
    msg = str(ctx['raw_message'])

    if re.match(r'.*?\[CQ:at,qq=.*?\]', msg):
        qq = re.findall(r'\[CQ:at,qq=(.*?)\]', msg)[0]
        if qq != "all":
            await session.send(f"[CQ:at,qq={int(qq)}] {text}")
            return

    await session.send(text)

def getStatus():
    file = open('D:/dl/started.json', 'r')
    statusDict = json.loads(str(file.read()))
    return statusDict['status']
