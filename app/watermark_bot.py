# -*- coding: utf-8 -*-
import asyncio
import hashlib
import logging
import os,shutil
import subprocess

import aiofiles #
import piexif #
from aiogram import Bot, Dispatcher, executor, types #
from aiogram.bot.api import TelegramAPIServer

logging.basicConfig(level=logging.ERROR)
local_server = TelegramAPIServer.from_base(os.getenv('BOTSERVER'))
bot = Bot(token=os.getenv('TOKEN'), server=local_server) #Docker
dp = Dispatcher(bot)

watermark_text = os.getenv('WATERMARK') #Docker
font_path = os.getcwd()+'/fonts/'+'Lato-Regular.ttf'


async def watermark(fname, new_fname, text, color, rotate):
    ffmpeg_filter = ':'.join([
        'drawtext=fontfile='+font_path,
        f"text='{text}'",
        f'fontcolor={color}@0.5',
        'fontsize=w*0.1',
        f'x=w-tw-h*0.12/6:y=h-th-h*0.12/6,rotate={rotate}'
    ])
    save_path = f'images/out/{color}/{new_fname}'

    p1 = subprocess.Popen(
        f'ffmpeg -i "{fname}" -vf "{ffmpeg_filter}" -y {save_path}',
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        shell=True
    )

    while True:
        try:
            p1.communicate(timeout=.1)
            break
        except subprocess.TimeoutExpired:
            await asyncio.sleep(1)
        except Exception as e:
            logging.info('Exception occured: ' + str(e))
            logging.info('Subprocess failed')
            return e

    return p1.returncode


def all_files_size():
    """Return the size of all images."""
    size = 0
    for dirpath, _dirnames, filenames in os.walk('images'):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            size += os.path.getsize(fp)
    return size


def md5(path):
    """Calculates the hash of images in chunks, since the picture may not fit into RAM."""
    with open(path, 'rb') as f:
        md5hash = hashlib.md5()
        for chunk in iter(lambda: f.read(4096), b''):
            md5hash.update(chunk)
    return md5hash.hexdigest()


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message):
    await message.answer('Send me an image as a document! Waiting you ⏳')


@dp.message_handler(content_types=[
    types.ContentType.ANIMATION,
    types.ContentType.DOCUMENT,
    types.ContentType.VIDEO
])
async def send_watermark(message):
    msg_file = message.video if message.content_type == 'video' else message.document
    file_type, file_ext = msg_file.mime_type.split('/')
    try:
        file = await bot.get_file(msg_file.file_id)
        downloaded_file = await bot.download_file(file.file_path)
    except Exception as e:
        await message.answer(e)
        return
    path = 'images/' + msg_file.file_id + '.' + file_ext
    async with aiofiles.open(path, 'wb') as f:
        await f.write(downloaded_file.read())

    fname = md5(path) + '.' + file_ext
    rotate = 0

    if fname not in os.listdir(os.getcwd()+'/images/out/black'):
        if file_type == 'image':
            try:
                exif_dict = piexif.load(path)
            except piexif.InvalidImageDataError:
                exif_dict = {}
            # Если в Exif есть тег Orientation, то поворачиваем изображение
            try:
                orientation = exif_dict['0th'][274]
            except KeyError:
                orientation = None
            rotate_values = {3: 'PI', 6: '3*PI/4', 8: 'PI/2'}
            if orientation in rotate_values:
                rotate = rotate_values[orientation]

    processing_msg = await message.answer('Processing...')
    for c in ('white'):
        code = await watermark(path, fname, watermark_text, c, rotate)
        if code:
            print(code)
            await message.answer('Something went wrong, please try again 😔')
            return
        wm_file = await aiofiles.open(f'images/out/{c}/{fname}', 'rb')
        await message.answer_document(wm_file)
    await processing_msg.delete()


@dp.message_handler(content_types=['photo'])
async def photo_handler(message):
    file = await bot.get_file(message.photo[-1].file_id)
    downloaded_file = await bot.download_file(file.file_path)
    path = os.getcwd()+'/images/' + file.file_path
    async with aiofiles.open(path, 'wb') as f:
        await f.write(downloaded_file.read())

    fname = md5(path)  + '.jpg'
    rotate = 0

    if fname not in os.listdir(os.getcwd()+'/images/out/black'):
        try:
            exif_dict = piexif.load(path)
        except piexif.InvalidImageDataError:
            exif_dict = {}
        try:
            orientation = exif_dict['0th'][274]
        except KeyError:
            orientation = None
        rotate_values = {3: 'PI', 6: '3*PI/4', 8: 'PI/2'}
        if orientation in rotate_values:
            rotate = rotate_values[orientation]

    for c in ('black', 'white'):
        code = await watermark(path, fname, watermark_text, c, rotate)
        if code:
            await message.answer('Something went wrong, please try again 😔')
            return
        wm_file = await aiofiles.open(f'images/out/{c}/{fname}', 'rb')
        await message.answer_photo(wm_file)

# Count data size #
@dp.message_handler(commands=['size'])
async def send_info(message):
    data_size = round(all_files_size() / 1048576, 2)
    await message.answer('Size of all photos: {} MB'.format(data_size))

# Clear all the data saved in the server #
@dp.message_handler(commands=['clear'])
async def send_info(message):
    shutil.rmtree(os.getcwd()+'/images')
    build_dirs()

# @dp.message_handler(commands=['setext'])
# async def set_text(message):
#     print(message)
#     message.inline_keyboard(row_width=1)

@dp.message_handler()
async def send_idk(message):
    await message.reply('So what should I do about it?')

def build_dirs():
    img_path = os.getcwd()+'/images'
    photo_path = os.getcwd()+'/images'+'/photos'

    if not(os.path.exists(img_path)):
        os.mkdir(img_path)
    if not(os.path.exists(photo_path)):
        os.mkdir(photo_path)
    
    out_path = img_path + '/out'
    if not(os.path.exists(out_path)):
        os.mkdir(out_path)
        
    if not(os.path.exists(out_path+'/white')):
        os.mkdir(out_path+'/white')
    if not(os.path.exists(out_path+'/black')):
        os.mkdir(out_path+'/black')

if __name__ == '__main__':
    build_dirs()

    print('Bot on Air')
    executor.start_polling(dp, skip_updates=True)