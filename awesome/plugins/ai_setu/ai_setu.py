import random
import re

import nonebot

from Services.ai_setu import AIImageGenerator
from Services.rate_limiter import UserLimitModifier
from Services.util.common_util import compile_forward_message
from Services.util.ctx_utility import get_group_id, get_nickname, get_user_id
from awesome.Constants import user_permission as perm
from awesome.plugins.setu.setu import HIGH_FREQ_KEYWORDS
from qq_bot_core import user_control_module, setu_control, global_rate_limiter

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)

ai_bot_stuff = AIImageGenerator()


@nonebot.on_command('色色替换', only_to_me=False)
async def add_sese_replace(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.OWNER):
        return

    args = session.current_arg.replace('，', ',')
    args = args.split(',')
    if len(args) != 2:
        await session.finish('Wrong usage.')
        return

    await ai_bot_stuff.add_high_confident_word(args)
    await session.finish('Done')


@nonebot.on_command('色色设置', only_to_me=False)
async def sese_configuration(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.OWNER):
        return

    args = session.current_arg.strip()
    if not args.isdigit():
        await session.finish('?')

    await global_rate_limiter.set_function_limit('ai_image', int(args))
    await session.finish('Done!')


@nonebot.on_command('清理缓存', only_to_me=False)
async def sese_cache_removal(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)

    if not get_privilege(user_id, perm.OWNER):
        return

    await ai_bot_stuff.delete_holder_data()
    await session.finish("It's done.")


@nonebot.on_command('色色点赞', only_to_me=False)
async def add_sese_applause(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    args = session.current_arg.strip()

    group_id = get_group_id(ctx)
    user_id = get_user_id(ctx)

    up_vote_result = await ai_bot_stuff.up_vote_uuid(args, user_id)
    if up_vote_result is not None and isinstance(up_vote_result, list):
        for tag in up_vote_result:
            cn_tag_name = await ai_bot_stuff.reverse_get_high_confident_word(tag)
            if cn_tag_name:
                setu_control.set_group_xp(group_id, cn_tag_name)
                setu_control.track_keyword(cn_tag_name)
                setu_control.set_user_xp(user_id, cn_tag_name, get_nickname(ctx))

        await session.finish('感谢投票~')

    if isinstance(up_vote_result, str):
        await session.finish('您已经投过票了')
    await session.finish('uid不对吧？')


@nonebot.on_command('色色', only_to_me=False)
async def ai_generating_image(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    message_id = ctx['message_id']
    group_id = get_group_id(ctx)
    user_id = get_user_id(ctx)

    bot = nonebot.get_bot()
    group_member_list = await bot.get_group_member_list(group_id=group_id)
    if len(group_member_list) > 100:
        user_limit = UserLimitModifier(60 * 60 * 24, 2.0)
        rate_limiter_check = await global_rate_limiter.user_group_limit_check('ai_image', user_id, group_id, user_limit)
    else:
        user_limit = UserLimitModifier(200, .8)
        rate_limiter_check = await global_rate_limiter.user_limit_check('ai_image', user_id, user_limit)

        user_limit = UserLimitModifier(60 * 60 * 24, 120, True)
        rate_limiter_check_temp = await global_rate_limiter.user_limit_check('ai_image_day', user_id, user_limit)
        if isinstance(rate_limiter_check_temp, str):
            rate_limiter_check = rate_limiter_check_temp

    if isinstance(rate_limiter_check, str):
        await session.finish(f'[CQ:reply,id={message_id}]{rate_limiter_check}')

    args = session.current_arg

    if args is None or not args:
        args = ','.join(random.sample(HIGH_FREQ_KEYWORDS, random.randint(2, 4)))

    args = args.replace('，', ',').replace('children', 'loli').replace('child', 'loli')
    args = re.sub(r'\s{2,}', '', args)

    args_list = args.split(',')
    new_arg_list = []
    replace_notification = ''
    for arg in args_list:
        if not arg:
            continue

        replacing_candidate = await ai_bot_stuff.replace_high_confident_word(arg)
        if replacing_candidate:
            if replacing_candidate == "''":
                replace_notification += f'\n已去除高危关键词{arg}'
            else:
                new_arg_list.append(replacing_candidate)
                replace_notification += f'\n替换关键词 {arg} 为高度自信关键词 {replacing_candidate}'
        else:
            new_arg_list.append(arg)

    new_arg_list = list(set(new_arg_list))

    args = ','.join(new_arg_list)
    if 'furry' in args:
        await session.finish('该AI模型不是用来生成furry图的，请期待其独立功能。')

    seed = random.randint(1, int(1 << 32 - 1))
    download_path, uid = await ai_bot_stuff.get_ai_generated_image(args, seed)

    confident_prompt = await ai_bot_stuff.get_tag_confident_worker(new_arg_list[:6])

    if download_path:
        group_id = get_group_id(ctx)
        hint_prompt = "\n建议使用英文tag搜索，多个tag可使用逗号隔开。" if not re.fullmatch(r"^[\sA-Za-z0-9,，_{}\[\]']+$", args) else ""

        message = f'[CQ:reply,id={message_id}]' \
                  f'[CQ:image,file=file:///{download_path}]' \
                  f'{hint_prompt}\n' \
                  f'Seed: {seed}\n'
        # f'keywords: {args}\n'

        await bot.send_group_forward_msg(
            group_id=group_id,
            messages=compile_forward_message(
                session.self_id,
                f'过滤信息：{replace_notification}',
                confident_prompt,
                message,
                f'如果您喜欢该生成结果，您可以用下面的命令给图片点赞！',
                f'！色色点赞 {uid}'
            )
        )

        nickname = get_nickname(ctx)
        if 'group_id' in ctx:
            setu_control.set_group_data(get_group_id(ctx), 'setu')
            setu_control.set_user_data(0, 'ai_setu', 'null', 1, True)

        setu_control.set_user_data(user_id, 'setu', nickname)

    else:
        await session.finish('加载失败，请重试！')