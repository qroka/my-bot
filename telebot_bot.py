import telebot
import os
import glob
from PIL import Image
import main
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
import tempfile
import uuid
import config
from deep_translator import GoogleTranslator
import re

bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)

user_headers = {}
user_landscape_orientation = {}  # Хранение выбора ориентации для каждого пользователя
user_search_query = {}  # Хранение поискового запроса пользователя
user_found_images = {}  # Хранение найденных изображений для каждого пользователя
user_state = {}  # Состояние пользователя в диалоге

def translate_to_english(text):
    """Переводит текст на английский язык для лучшего поиска"""
    try:
        # Простая проверка - если текст содержит только латинские буквы, считаем что он на английском
        if re.match(r'^[a-zA-Z\s\-.,!?]+$', text.strip()):
            print(f"Текст похож на английский: {text}")
            return text, text
        
        # Переводим на английский используя GoogleTranslator
        translator = GoogleTranslator(source='auto', target='en')
        english_text = translator.translate(text)
        
        print(f"Перевод: '{text}' -> '{english_text}'")
        return text, english_text
        
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        # Если перевод не удался, возвращаем оригинальный текст
        return text, text

def search_images_unsplash(query, max_results=10):
    """Поиск изображений через Unsplash API с использованием простых HTTP запросов"""
    try:
        # URL для поиска изображений
        url = "https://api.unsplash.com/search/photos"
        
        # Заголовки для авторизации
        headers = {
            "Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}",
            "Accept-Version": "v1"
        }
        
        # Параметры запроса
        params = {
            "query": query,
            "page": 1,
            "per_page": min(max_results, 30),  # Unsplash позволяет максимум 30 на страницу
            "orientation": "landscape"  # Предпочитаем горизонтальные изображения
        }
        
        # Выполняем запрос
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('results'):
            return []
        
        # Преобразуем результаты в удобный формат
        images = []
        for photo in data['results']:
            image_info = {
                'image': photo['urls'].get(config.IMAGE_QUALITY, photo['urls']['regular']),
                'title': photo.get('description') or photo.get('alt_description', 'Изображение'),
                'source': f"Unsplash - {photo['user']['name']}",
                'id': photo['id'],
                'width': photo['width'],
                'height': photo['height']
            }
            images.append(image_info)
        
        return images
    except requests.exceptions.RequestException as e:
        print(f"Ошибка HTTP запроса к Unsplash: {e}")
        return []
    except Exception as e:
        print(f"Ошибка поиска изображений в Unsplash: {e}")
        return []

def download_image(url, timeout=10):
    """Скачивание изображения по URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # Проверяем, что это изображение
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            return None
            
        return response.content
    except Exception as e:
        print(f"Ошибка скачивания изображения {url}: {e}")
        return None

def create_image_choice_keyboard():
    """Создает клавиатуру выбора: есть изображение или нужно найти"""
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ У меня есть изображение", callback_data="have_image")
    )
    keyboard.row(
        InlineKeyboardButton("🔍 Найти изображение", callback_data="search_image")
    )
    return keyboard

def create_image_approval_keyboard():
    """Создает клавиатуру для подтверждения найденного изображения"""
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ Подходит", callback_data="approve_image"),
        InlineKeyboardButton("❌ Найти другое", callback_data="search_another")
    )
    return keyboard

def create_temp_image_file(image_data, user_id):
    """Создает временный файл изображения из данных"""
    try:
        # Создаем временную папку для пользователя
        temp_dir = f"temp_found_{user_id}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Сохраняем изображение
        temp_path = os.path.join(temp_dir, f"found_image_{uuid.uuid4().hex}.jpg")
        with open(temp_path, 'wb') as f:
            f.write(image_data)
        
        return temp_path
    except Exception as e:
        print(f"Ошибка создания временного файла: {e}")
        return None

def process_found_image_automatically(user_id, chat_id):
    """Автоматическая обработка найденного изображения"""
    try:
        if user_id not in user_found_images or user_id not in user_headers:
            return False
        
        # Отправляем сообщение о начале обработки
        processing_msg = bot.send_message(chat_id, "🔄 Обрабатываю найденное изображение...")
        
        # Создаем фиктивное сообщение для совместимости с process_image_file
        class FakeMessage:
            def __init__(self, chat_id):
                self.chat = type('Chat', (), {'id': chat_id})()
        
        fake_message = FakeMessage(chat_id)
        
        # Создаем фиктивный file_info
        class FakeFileInfo:
            def __init__(self):
                self.file_path = "found_image.jpg"
        
        file_info = FakeFileInfo()
        found_data = user_found_images[user_id]['data']
        
        # Обрабатываем изображение
        success = process_image_file(fake_message, file_info, user_id, found_data)
        
        if success:
            # Удаляем сообщение о обработке
            try:
                bot.delete_message(chat_id, processing_msg.message_id)
            except:
                pass
        
        return success
        
    except Exception as e:
        print(f"Ошибка автоматической обработки: {e}")
        bot.send_message(chat_id, f"❌ Ошибка обработки: {str(e)}")
        return False

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 
        "Привет! Я бот для создания красивых изображений с заголовками.\n\n"
        "📱 Создаю изображения для соцсетей (2160x2160)\n"
        "💼 Создаю изображения для инвестпортала (2310x1200) в 3 вариантах ориентации\n"
        "🔍 Могу найти качественные изображения с Unsplash\n"
        "🌐 Автоматически перевожу запросы поиска на английский\n\n"
        "Отправь мне заголовок (текст), который нужно добавить на фото.")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id,
        "📋 Как использовать бота:\n\n"
        "1️⃣ Отправь заголовок (текст)\n"
        "2️⃣ Выбери источник изображения:\n"
        "   • ✅ У меня есть изображение - загрузи свое фото\n"
        "   • 🔍 Найти изображение - бот найдет подходящее\n"
        "3️⃣ Если выбрал поиск:\n"
        "   • Напиши тему для поиска (на любом языке!)\n"
        "   • Бот автоматически переведет запрос на английский\n"
        "   • Получи качественное фото с Unsplash\n"
        "   • Подтверди найденное изображение или найди другое\n"
        "4️⃣ Выбери режим обработки:\n"
        "   • 📱 Только для соцсетей - создаст квадратное изображение\n"
        "   • 📱 Для соцсетей + 💼 Для инвестпортала - выбери ориентацию\n"
        "   • 💼 Только для инвестпортала - выбери ориентацию\n"
        "5️⃣ Если у тебя свое изображение - отправь фотографию или файл:\n"
        "   • Фото - будет сжато Telegram\n"
        "   • Файл - без сжатия, лучшее качество\n"
        "6️⃣ Получи результат:\n"
        "   • 📱 Для соцсетей (2160x2160) как файл\n"
        "   • 💼 Варианты для инвестпортала (2310x1200):\n"
        "     - По центру\n"
        "     - По верху\n"
        "     - По низу\n\n"
        "Команды:\n"
        "/start - Начать работу\n"
        "/help - Показать справку")

@bot.message_handler(content_types=['text'])
def get_text(message):
    if message.text.startswith('/'):
        return
    
    user_id = message.from_user.id
    
    # Проверяем состояние пользователя
    current_state = user_state.get(user_id, 'waiting_header')
    
    if current_state == 'waiting_header':
        # Сохраняем заголовок
        user_headers[user_id] = message.text
        user_landscape_orientation[user_id] = 'bottom'  # По умолчанию
        user_state[user_id] = 'choosing_image_source'
        
        bot.send_message(message.chat.id, 
            f"✅ Заголовок сохранен: \"{message.text}\"\n\n"
            "У вас уже есть изображение для новости?",
            reply_markup=create_image_choice_keyboard())
    
    elif current_state == 'waiting_search_query':
        # Сохраняем поисковый запрос и ищем изображения
        user_search_query[user_id] = message.text
        
        # Переводим запрос на английский для лучшего поиска
        original_query, english_query = translate_to_english(message.text)
        
        # Показываем сообщение о переводе, если он был выполнен
        if original_query != english_query:
            bot.send_message(message.chat.id, 
                f"🔄 Перевожу запрос для лучшего поиска:\n"
                f"'{original_query}' → '{english_query}'\n\n"
                f"🔍 Ищу подходящие изображения...")
        else:
            bot.send_message(message.chat.id, "🔍 Ищу подходящие изображения...")
        
        # Ищем изображения по переведенному запросу
        images = search_images_unsplash(english_query, max_results=config.DEFAULT_SEARCH_RESULTS)
        
        if not images:
            bot.send_message(message.chat.id, 
                "❌ К сожалению, не удалось найти подходящие изображения.\n"
                "Попробуйте другой поисковый запрос или загрузите свое изображение.",
                reply_markup=create_image_choice_keyboard())
            user_state[user_id] = 'choosing_image_source'
            return
        
        # Пробуем скачать первое подходящее изображение
        downloaded_image = None
        selected_image_info = None
        
        for img_info in images:
            try:
                img_url = img_info.get('image')
                if img_url:
                    downloaded_image = download_image(img_url)
                    if downloaded_image:
                        selected_image_info = img_info
                        break
            except Exception as e:
                print(f"Ошибка при скачивании: {e}")
                continue
        
        if not downloaded_image:
            bot.send_message(message.chat.id, 
                "❌ Не удалось скачать найденные изображения.\n"
                "Попробуйте другой поисковый запрос или загрузите свое изображение.",
                reply_markup=create_image_choice_keyboard())
            user_state[user_id] = 'choosing_image_source'
            return
        
        # Сохраняем найденное изображение
        user_found_images[user_id] = {
            'data': downloaded_image,
            'info': selected_image_info
        }
        user_state[user_id] = 'approving_image'
        
        # Показываем найденное изображение
        try:
            if original_query != english_query:
                caption_text = f"🔍 Найдено изображение по запросу:\n"
                caption_text += f"🇷🇺 '{original_query}' → 🇺🇸 '{english_query}'\n\n"
            else:
                caption_text = f"🔍 Найдено изображение по запросу: \"{message.text}\"\n\n"
            
            if selected_image_info:
                caption_text += f"📷 {selected_image_info.get('source', 'Unsplash')}\n"
                if selected_image_info.get('title'):
                    caption_text += f"📝 {selected_image_info['title']}\n"
            caption_text += "\nЭто изображение вам подходит?"
            
            bot.send_photo(message.chat.id, downloaded_image, 
                caption=caption_text,
                reply_markup=create_image_approval_keyboard())
        except Exception as e:
            print(f"Ошибка отправки изображения: {e}")
            bot.send_message(message.chat.id, 
                "Найдено изображение, но возникла ошибка при его отправке.\n"
                "Продолжить с этим изображением?",
                reply_markup=create_image_approval_keyboard())
    
    else:
        # Сбрасываем состояние и начинаем заново
        user_state[user_id] = 'waiting_header'
        user_headers[user_id] = message.text
        user_landscape_orientation[user_id] = 'bottom'
        user_state[user_id] = 'choosing_image_source'
        
        bot.send_message(message.chat.id, 
            f"✅ Заголовок сохранен: \"{message.text}\"\n\n"
            "У вас уже есть изображение для новости?",
            reply_markup=create_image_choice_keyboard())

def safe_edit_message(chat_id, message_id, new_text):
    """Безопасное редактирование сообщения с проверкой изменений"""
    try:
        bot.edit_message_text(new_text, chat_id=chat_id, message_id=message_id)
        return True
    except telebot.apihelper.ApiException as e:
        if "message is not modified" in str(e):
            # Сообщение не изменилось, это нормально
            return True
        else:
            # Другая ошибка API
            print(f"API Error: {e}")
            return False
    except Exception as e:
        print(f"Edit message error: {e}")
        return False

def process_image_file(message, file_info, user_id, found_image_data=None):
    """Обработка изображения из файла или фото"""
    try:
        # Используем найденное изображение или скачиваем файл пользователя
        if found_image_data:
            downloaded_file = found_image_data
        else:
            downloaded_file = bot.download_file(file_info.file_path)
        
        # Создаем временные папки
        temp_img_dir = f"temp_img_{user_id}"
        temp_logo_dir = f"temp_logo_{user_id}"
        temp_output_dir = f"temp_output_{user_id}"
        
        os.makedirs(temp_img_dir, exist_ok=True)
        os.makedirs(temp_logo_dir, exist_ok=True)
        os.makedirs(temp_output_dir, exist_ok=True)
        
        # Определяем расширение файла
        if found_image_data:
            file_ext = '.jpg'  # Для найденных изображений используем jpg
        else:
            file_ext = os.path.splitext(file_info.file_path)[1].lower()
            if not file_ext:
                file_ext = '.jpg'  # По умолчанию
        
        # Сохраняем файл пользователя
        input_path = os.path.join(temp_img_dir, f"user_image{file_ext}")
        with open(input_path, 'wb') as f:
            f.write(downloaded_file)
        
        # Копируем логотип из основной папки
        logo_files = glob.glob(os.path.join(main.LOGO_DIR, '*'))
        if not logo_files:
            bot.send_message(message.chat.id, "❌ Ошибка: логотип не найден!")
            return False
        
        logo_path = os.path.join(temp_logo_dir, "logo.png")
        logo_img = Image.open(logo_files[0])
        logo_img.save(logo_path)
        
        # Загружаем логотип
        logo_img = main.safe_open_image(logo_path)
        if logo_img is None:
            bot.send_message(message.chat.id, "❌ Ошибка: не удалось загрузить логотип!")
            return False
        
        # Определяем режим обработки
        orientation = user_landscape_orientation.get(user_id, 'bottom')
        print(f"DEBUG: process_image_file: orientation={orientation}")
        
        if orientation == 'social_only':
            # Создаем только изображение для соцсетей
            success = main.process_single_image_social_only(input_path, logo_img, user_headers[user_id])
        elif orientation.startswith('both_'):
            # Для соцсетей + инвестпортала с выбранной ориентацией
            landscape_orientation = orientation.split('_')[1]
            landscape_config = {
                'center': main.CONFIG_LANDSCAPE_CENTER,
                'top': main.CONFIG_LANDSCAPE_TOP,
                'bottom': main.CONFIG_LANDSCAPE_BOTTOM
            }.get(landscape_orientation, main.CONFIG_LANDSCAPE_BOTTOM)
            print(f"DEBUG: Режим 'both': выбрана ориентация '{landscape_orientation}', конфигурация: {landscape_config.get('image_alignment', 'unknown')}")
            print(f"DEBUG: landscape_config = {landscape_config}")
            success = main.process_single_image(input_path, logo_img, user_headers[user_id], landscape_config)
        elif orientation.startswith('investor_only_'):
            # Только для инвестпортала с выбранной ориентацией
            landscape_orientation = orientation.split('_')[2]  # Берем третий элемент: investor_only_center -> center
            print(f"DEBUG: investor_only: landscape_orientation = {landscape_orientation}")
            print(f"DEBUG: investor_only: main.CONFIG_LANDSCAPE_CENTER = {main.CONFIG_LANDSCAPE_CENTER}")
            landscape_config = {
                'center': main.CONFIG_LANDSCAPE_CENTER,
                'top': main.CONFIG_LANDSCAPE_TOP,
                'bottom': main.CONFIG_LANDSCAPE_BOTTOM
            }.get(landscape_orientation, main.CONFIG_LANDSCAPE_BOTTOM)
            print(f"DEBUG: investor_only: выбранная конфигурация = {landscape_config}")
            success = main.process_single_image_investor_only_single(input_path, logo_img, user_headers[user_id], landscape_config)

        
        if success:
            # Отправляем результаты
            bot.send_message(message.chat.id, "✅ Обработка завершена! Отправляю результаты...")
            
            # Показываем все файлы в папке output для отладки
            all_files = os.listdir(main.OUTPUT_DIR)
            print(f"DEBUG: Все файлы в папке output после обработки: {all_files}")
            
            # Получаем базовое имя файла без расширения
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            print(f"DEBUG: base_name = {base_name}")
            print(f"DEBUG: input_path = {input_path}")
            
            # Определяем названия ориентаций (используется во всех режимах)
            orientation_names = {
                'center': 'по центру',
                'top': 'по верху', 
                'bottom': 'по низу'
            }
            
            # Отправляем результаты в зависимости от выбранного режима
            if orientation == 'social_only':
                # Отправляем только изображение для соцсетей
                square_path = os.path.join(main.OUTPUT_DIR, f"{base_name}_square.png")
                if os.path.exists(square_path):
                    with open(square_path, 'rb') as f:
                        bot.send_document(message.chat.id, f, 
                                       caption="📱 Для соцсетей (2160x2160)")
                else:
                    bot.send_message(message.chat.id, "⚠️ Изображение для соцсетей не найдено")
                
                bot.send_message(message.chat.id, 
                    "🎉 Готово! Обработано изображение с заголовком:\n"
                    f"\"{user_headers[user_id]}\"\n\n"
                    f"📱 Для соцсетей (2160x2160)\n\n"
                    "Отправь новый заголовок для следующего изображения.")
            
            elif orientation.startswith('both_'):
                # Отправляем изображение для соцсетей
                square_path = os.path.join(main.OUTPUT_DIR, f"{base_name}_square.png")
                if os.path.exists(square_path):
                    with open(square_path, 'rb') as f:
                        bot.send_document(message.chat.id, f, 
                                       caption="📱 Для соцсетей (2160x2160)")
                else:
                    bot.send_message(message.chat.id, "⚠️ Изображение для соцсетей не найдено")
                
                # Отправляем изображение для инвестпортала с выбранной ориентацией
                landscape_orientation = orientation.split('_')[1]
                landscape_path = os.path.join(main.OUTPUT_DIR, f"{base_name}_landscape_{landscape_orientation}.png")
                print(f"DEBUG: Ищем файл: {landscape_path}")
                print(f"DEBUG: Файл существует: {os.path.exists(landscape_path)}")
                if os.path.exists(landscape_path):
                    with open(landscape_path, 'rb') as f:
                        orientation_name = orientation_names.get(landscape_orientation, 'по низу')
                        bot.send_document(message.chat.id, f, 
                                       caption=f"💼 Для инвестпортала (2310x1200) - {orientation_name}")
                else:
                    bot.send_message(message.chat.id, "⚠️ Изображение для инвестпортала не найдено")
                    # Показываем все файлы в папке для отладки
                    all_files = os.listdir(main.OUTPUT_DIR)
                    print(f"DEBUG: Все файлы в папке output: {all_files}")
                    print(f"DEBUG: Ищем файл с базовым именем: {base_name}")
                
                # Определяем название ориентации для сообщения
                orientation_name = orientation_names.get(landscape_orientation, 'по низу')
                
                bot.send_message(message.chat.id, 
                    "🎉 Готово! Обработано изображение с заголовком:\n"
                    f"\"{user_headers[user_id]}\"\n\n"
                    f"📱 Для соцсетей (2160x2160)\n"
                    f"💼 Для инвестпортала (2310x1200) - {orientation_name}\n\n"
                    "Отправь новый заголовок для следующего изображения.")
            
            elif orientation.startswith('investor_only_'):
                # Отправляем только изображение для инвестпортала с выбранной ориентацией
                landscape_orientation = orientation.split('_')[2]  # Берем третий элемент: investor_only_center -> center
                landscape_path = os.path.join(main.OUTPUT_DIR, f"{base_name}_landscape_{landscape_orientation}.png")
                if os.path.exists(landscape_path):
                    with open(landscape_path, 'rb') as f:
                        orientation_name = orientation_names.get(landscape_orientation, 'по низу')
                        bot.send_document(message.chat.id, f, 
                                       caption=f"💼 Для инвестпортала (2310x1200) - {orientation_name}")
                else:
                    bot.send_message(message.chat.id, "⚠️ Изображение для инвестпортала не найдено")
                
                # Определяем название ориентации для сообщения
                orientation_name = orientation_names.get(landscape_orientation, 'по низу')
                
                bot.send_message(message.chat.id, 
                    "🎉 Готово! Обработано изображение с заголовком:\n"
                    f"\"{user_headers[user_id]}\"\n\n"
                    f"💼 Для инвестпортала (2310x1200) - {orientation_name}\n\n"
                    "Отправь новый заголовок для следующего изображения.")
            

            
            return True
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при обработке изображения!")
            return False
    
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка обработки: {str(e)}")
        bot.send_message(message.chat.id, 
            "Произошла ошибка. Попробуй еще раз или обратись к администратору.")
        return False
    
    finally:
        # Очищаем временные файлы
        try:
            if 'temp_img_dir' in locals():
                for file in os.listdir(temp_img_dir):
                    os.remove(os.path.join(temp_img_dir, file))
                os.rmdir(temp_img_dir)
            
            if 'temp_logo_dir' in locals():
                for file in os.listdir(temp_logo_dir):
                    os.remove(os.path.join(temp_logo_dir, file))
                os.rmdir(temp_logo_dir)
            
            if 'temp_output_dir' in locals():
                for file in os.listdir(temp_output_dir):
                    os.remove(os.path.join(temp_output_dir, file))
                os.rmdir(temp_output_dir)
        except:
            pass
        
def create_orientation_keyboard():
    """Создает клавиатуру с выбором режима обработки"""
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("📱 Только для соцсетей", callback_data="social_only")
    )
    keyboard.row(
        InlineKeyboardButton("📱 Для соцсетей + 💼 Для инвестпортала", callback_data="both")
    )
    keyboard.row(
        InlineKeyboardButton("💼 Только для инвестпортала", callback_data="investor_only")
    )
    return keyboard

def create_landscape_orientation_keyboard():
    """Создает клавиатуру с выбором ориентации для инвестпортала"""
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("💼 По центру", callback_data="orientation_center"),
        InlineKeyboardButton("💼 По верху", callback_data="orientation_top")
    )
    keyboard.row(
        InlineKeyboardButton("💼 По низу", callback_data="orientation_bottom")
    )
    return keyboard

@bot.callback_query_handler(func=lambda call: call.data in ['have_image', 'search_image'])
def handle_image_source_choice(call):
    """Обработка выбора источника изображения"""
    user_id = call.from_user.id
    
    if user_id not in user_headers:
        bot.answer_callback_query(call.id, "Сначала отправь заголовок!")
        return
    
    choice = call.data
    
    if choice == 'have_image':
        # Пользователь имеет свое изображение
        user_state[user_id] = 'choosing_orientation'
        bot.answer_callback_query(call.id, "Продолжим с вашим изображением")
        bot.edit_message_text(
            f"✅ Хорошо! Будем использовать ваше изображение.\n\n"
            f"Заголовок: \"{user_headers[user_id]}\"\n\n"
            "Выберите, для чего создавать изображения:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=create_orientation_keyboard()
        )
    
    elif choice == 'search_image':
        # Пользователь хочет найти изображение
        user_state[user_id] = 'waiting_search_query'
        bot.answer_callback_query(call.id, "Напишите тему для поиска")
        bot.edit_message_text(
            f"🔍 Хорошо! Найдем подходящее изображение.\n\n"
            f"Заголовок: \"{user_headers[user_id]}\"\n\n"
            "Напишите тему или описание изображения на любом языке.\n"
            "Примеры: \"технологии\", \"бизнес\", \"финансы\", \"офис\", \"команда\", \"успех\" и т.д.\n\n"
            "🌐 Я автоматически переведу ваш запрос на английский для лучшего поиска!",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data in ['approve_image', 'search_another'])
def handle_image_approval(call):
    """Обработка подтверждения найденного изображения"""
    user_id = call.from_user.id
    
    if user_id not in user_headers:
        bot.answer_callback_query(call.id, "Сначала отправь заголовок!")
        return
    
    choice = call.data
    
    if choice == 'approve_image':
        # Пользователь одобрил изображение
        user_state[user_id] = 'choosing_orientation_found'
        bot.answer_callback_query(call.id, "Изображение выбрано!")
        bot.edit_message_caption(
            f"✅ Отлично! Изображение выбрано.\n\n"
            f"Заголовок: \"{user_headers[user_id]}\"\n\n"
            "Теперь выберите, для чего создавать изображения:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=create_orientation_keyboard()
        )
    
    elif choice == 'search_another':
        # Пользователь хочет найти другое изображение
        user_state[user_id] = 'waiting_search_query'
        bot.answer_callback_query(call.id, "Введите новый поисковый запрос")
        bot.edit_message_caption(
            f"🔍 Попробуем найти другое изображение.\n\n"
            f"Заголовок: \"{user_headers[user_id]}\"\n\n"
            "Напишите новую тему или описание изображения (на любом языке):\n\n"
            "🌐 Я автоматически переведу ваш запрос для лучшего поиска!",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data in ['social_only', 'both', 'investor_only'])
def handle_processing_choice(call):
    """Обработка выбора режима обработки"""
    user_id = call.from_user.id
    
    if user_id not in user_headers:
        bot.answer_callback_query(call.id, "Сначала отправь заголовок!")
        return
    
    choice = call.data
    
    if choice == 'social_only':
        # Только для соцсетей
        user_landscape_orientation[user_id] = 'social_only'
        bot.answer_callback_query(call.id, "Выбрано создание только для соцсетей")
        
        # Проверяем, есть ли найденное изображение для автоматической обработки
        if user_id in user_found_images:
            # Автоматически обрабатываем найденное изображение
            # Проверяем, есть ли изображение в сообщении
            if call.message.photo:
                # Если есть фото, используем edit_message_caption
                bot.edit_message_caption(
                    f"✅ Выбрано создание только для соцсетей!\n\n"
                    f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                    "Запускаю обработку найденного изображения...\n\n"
                    "Бот создаст:\n"
                    "📱 Изображение для соцсетей (2160x2160)",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode='Markdown'
                )
            else:
                # Если нет фото, используем edit_message_text
                bot.edit_message_text(
                    f"✅ Выбрано создание только для соцсетей!\n\n"
                    f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                    "Запускаю обработку найденного изображения...\n\n"
                    "Бот создаст:\n"
                    "📱 Изображение для соцсетей (2160x2160)",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode='Markdown'
                )
            
            # Запускаем автоматическую обработку
            success = process_found_image_automatically(user_id, call.message.chat.id)
            
            if success:
                # Очищаем данные пользователя после успешной обработки
                user_headers.pop(user_id, None)
                user_landscape_orientation.pop(user_id, None)
                user_search_query.pop(user_id, None)
                user_found_images.pop(user_id, None)
                user_state.pop(user_id, None)
        else:
            # Просим пользователя загрузить свое изображение
            # Проверяем, есть ли изображение в сообщении
            if call.message.photo:
                # Если есть фото, используем edit_message_caption
                bot.edit_message_caption(
                    f"✅ Выбрано создание только для соцсетей!\n\n"
                    f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                    "Теперь отправь мне фотографию или файл изображения.\n\n"
                    "Бот создаст:\n"
                    "📱 Изображение для соцсетей (2160x2160)",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode='Markdown'
                )
            else:
                # Если нет фото, используем edit_message_text
                bot.edit_message_text(
                    f"✅ Выбрано создание только для соцсетей!\n\n"
                    f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                    "Теперь отправь мне фотографию или файл изображения.\n\n"
                    "Бот создаст:\n"
                    "📱 Изображение для соцсетей (2160x2160)",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode='Markdown'
                )
    
    elif choice == 'both':
        # Для соцсетей + инвестпортала - спрашиваем ориентацию
        user_landscape_orientation[user_id] = 'both'
        bot.answer_callback_query(call.id, "Выбери ориентацию для инвестпортала")
        
        # Проверяем, есть ли изображение в сообщении
        if call.message.photo:
            # Если есть фото, используем edit_message_caption
            bot.edit_message_caption(
                f"✅ Выбрано создание для соцсетей + инвестпортала!\n\n"
                f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                "Теперь выбери ориентацию для инвестпортала:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown',
                reply_markup=create_landscape_orientation_keyboard()
            )
        else:
            # Если нет фото, используем edit_message_text
            bot.edit_message_text(
                f"✅ Выбрано создание для соцсетей + инвестпортала!\n\n"
                f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                "Теперь выбери ориентацию для инвестпортала:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown',
                reply_markup=create_landscape_orientation_keyboard()
            )
    
    elif choice == 'investor_only':
        # Только для инвестпортала - спрашиваем ориентацию
        user_landscape_orientation[user_id] = 'investor_only'
        bot.answer_callback_query(call.id, "Выбери ориентацию для инвестпортала")
        
        # Проверяем, есть ли изображение в сообщении
        if call.message.photo:
            # Если есть фото, используем edit_message_caption
            bot.edit_message_caption(
                f"✅ Выбрано создание только для инвестпортала!\n\n"
                f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                "Теперь выбери ориентацию для инвестпортала:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown',
                reply_markup=create_landscape_orientation_keyboard()
            )
        else:
            # Если нет фото, используем edit_message_text
            bot.edit_message_text(
                f"✅ Выбрано создание только для инвестпортала!\n\n"
                f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                "Теперь выбери ориентацию для инвестпортала:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown',
                reply_markup=create_landscape_orientation_keyboard()
            )

@bot.callback_query_handler(func=lambda call: call.data.startswith('orientation_'))
def handle_landscape_orientation_choice(call):
    """Обработка выбора ориентации для инвестпортала"""
    user_id = call.from_user.id
    
    if user_id not in user_headers:
        bot.answer_callback_query(call.id, "Сначала отправь заголовок!")
        return
    
    # Определяем названия ориентаций (используется во всех режимах)
    orientation_names = {
        'center': 'по центру',
        'top': 'по верху', 
        'bottom': 'по низу'
    }
    
    # Определяем выбранную ориентацию
    orientation = call.data.split('_')[1]
    
    # Проверяем, какой режим был выбран ранее
    current_mode = user_landscape_orientation.get(user_id, '')
    
    if current_mode == 'both':
        user_landscape_orientation[user_id] = f'both_{orientation}'
        mode_text = "соцсетей + инвестпортала"
        result_text = f"📱 Изображение для соцсетей (2160x2160)\n💼 Изображение для инвестпортала (2310x1200) - {orientation_names[orientation]}"
    elif current_mode == 'investor_only':
        user_landscape_orientation[user_id] = f'investor_only_{orientation}'
        mode_text = "только для инвестпортала"
        result_text = f"💼 Изображение для инвестпортала (2310x1200) - {orientation_names[orientation]}"
    else:
        # Fallback для обратной совместимости
        user_landscape_orientation[user_id] = f'both_{orientation}'
        mode_text = "соцсетей + инвестпортала"
        result_text = f"📱 Изображение для соцсетей (2160x2160)\n💼 Изображение для инвестпортала (2310x1200) - {orientation_names[orientation]}"
    
    bot.answer_callback_query(call.id, f"Выбрана ориентация: {orientation_names[orientation]}")
    
    # Проверяем, есть ли найденное изображение для автоматической обработки
    if user_id in user_found_images:
        # Автоматически обрабатываем найденное изображение
        # Проверяем, есть ли изображение в сообщении
        if call.message.photo:
            # Если есть фото, используем edit_message_caption
            bot.edit_message_caption(
                f"✅ Выбрана ориентация для инвестпортала: **{orientation_names[orientation]}**\n\n"
                f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                f"Запускаю обработку найденного изображения...\n\n"
                f"Бот создаст для {mode_text}:\n"
                f"{result_text}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            # Если нет фото, используем edit_message_text
            bot.edit_message_text(
                f"✅ Выбрана ориентация для инвестпортала: **{orientation_names[orientation]}**\n\n"
                f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                f"Запускаю обработку найденного изображения...\n\n"
                f"Бот создаст для {mode_text}:\n"
                f"{result_text}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown'
            )
        
        # Запускаем автоматическую обработку
        success = process_found_image_automatically(user_id, call.message.chat.id)
        
        if success:
            # Очищаем данные пользователя после успешной обработки
            user_headers.pop(user_id, None)
            user_landscape_orientation.pop(user_id, None)
            user_search_query.pop(user_id, None)
            user_found_images.pop(user_id, None)
            user_state.pop(user_id, None)
    else:
        # Просим пользователя загрузить свое изображение
        # Проверяем, есть ли изображение в сообщении
        if call.message.photo:
            # Если есть фото, используем edit_message_caption
            bot.edit_message_caption(
                f"✅ Выбрана ориентация для инвестпортала: **{orientation_names[orientation]}**\n\n"
                f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                "Теперь отправь мне фотографию или файл изображения.\n\n"
                f"Бот создаст для {mode_text}:\n"
                f"{result_text}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            # Если нет фото, используем edit_message_text
            bot.edit_message_text(
                f"✅ Выбрана ориентация для инвестпортала: **{orientation_names[orientation]}**\n\n"
                f"Заголовок: \"{user_headers[user_id]}\"\n\n"
                "Теперь отправь мне фотографию или файл изображения.\n\n"
                f"Бот создаст для {mode_text}:\n"
                f"{result_text}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown'
            )

@bot.message_handler(content_types=['photo'])
def get_photo(message):
    user_id = message.from_user.id
    if user_id not in user_headers:
        bot.send_message(message.chat.id, "Сначала отправь заголовок!")
        return
    
    # Проверяем состояние пользователя
    current_state = user_state.get(user_id, 'choosing_orientation')
    if current_state not in ['choosing_orientation', 'choosing_orientation_found']:
        bot.send_message(message.chat.id, "Сначала выберите, откуда взять изображение!")
        return
    
    # Отправляем сообщение о начале обработки
    processing_msg = bot.send_message(message.chat.id, "🔄 Обрабатываю изображение...")
    
    try:
        # Проверяем, нужно ли использовать найденное изображение
        if current_state == 'choosing_orientation_found' and user_id in user_found_images:
            # Используем найденное изображение
            found_data = user_found_images[user_id]['data']
            # Создаем фиктивный file_info для найденного изображения
            class FakeFileInfo:
                def __init__(self):
                    self.file_path = "found_image.jpg"
            
            file_info = FakeFileInfo()
            success = process_image_file(message, file_info, user_id, found_data)
        else:
            # Используем загруженное пользователем изображение
            file_info = bot.get_file(message.photo[-1].file_id)
            if not file_info.file_path:
                bot.send_message(message.chat.id, "❌ Ошибка: не удалось получить путь к файлу фото.")
                return
            
            success = process_image_file(message, file_info, user_id)
        
        if success:
            # Удаляем сообщение о обработке
            try:
                bot.delete_message(message.chat.id, processing_msg.message_id)
            except:
                pass
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка обработки: {str(e)}")
        bot.send_message(message.chat.id, 
            "Произошла ошибка. Попробуй еще раз или обратись к администратору.")
    
    finally:
        # Очищаем все данные пользователя
        user_headers.pop(user_id, None)
        user_landscape_orientation.pop(user_id, None)
        user_search_query.pop(user_id, None)
        user_found_images.pop(user_id, None)
        user_state.pop(user_id, None)

@bot.message_handler(content_types=['document'])
def get_document(message):
    user_id = message.from_user.id
    if user_id not in user_headers:
        bot.send_message(message.chat.id, "Сначала отправь заголовок!")
        return
    
    # Проверяем состояние пользователя
    current_state = user_state.get(user_id, 'choosing_orientation')
    if current_state not in ['choosing_orientation', 'choosing_orientation_found']:
        bot.send_message(message.chat.id, "Сначала выберите, откуда взять изображение!")
        return
    
    # Проверяем, что это изображение
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
    file_ext = os.path.splitext(message.document.file_name)[1].lower()
    
    if file_ext not in allowed_extensions:
        bot.send_message(message.chat.id, 
            f"❌ Неподдерживаемый формат файла: {file_ext}\n\n"
            f"Поддерживаемые форматы: {', '.join(allowed_extensions)}")
        return
    
    # Отправляем сообщение о начале обработки
    processing_msg = bot.send_message(message.chat.id, "🔄 Обрабатываю файл изображения...")
    
    try:
        # Проверяем, нужно ли использовать найденное изображение
        if current_state == 'choosing_orientation_found' and user_id in user_found_images:
            # Используем найденное изображение
            found_data = user_found_images[user_id]['data']
            # Создаем фиктивный file_info для найденного изображения
            class FakeFileInfo:
                def __init__(self):
                    self.file_path = "found_image.jpg"
            
            file_info = FakeFileInfo()
            success = process_image_file(message, file_info, user_id, found_data)
        else:
            # Используем загруженное пользователем изображение
            file_info = bot.get_file(message.document.file_id)
            if not file_info.file_path:
                bot.send_message(message.chat.id, "❌ Ошибка: не удалось получить путь к файлу.")
                return
            
            success = process_image_file(message, file_info, user_id)
        
        if success:
            # Удаляем сообщение о обработке
            try:
                bot.delete_message(message.chat.id, processing_msg.message_id)
            except:
                pass
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка обработки: {str(e)}")
        bot.send_message(message.chat.id, 
            "Произошла ошибка. Попробуй еще раз или обратись к администратору.")
    
    finally:
        # Очищаем все данные пользователя
        user_headers.pop(user_id, None)
        user_landscape_orientation.pop(user_id, None)
        user_search_query.pop(user_id, None)
        user_found_images.pop(user_id, None)
        user_state.pop(user_id, None)

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    if not message.text.startswith('/'):
        # Очищаем предыдущие данные пользователя
        user_id = message.from_user.id
        user_headers.pop(user_id, None)
        user_landscape_orientation.pop(user_id, None)
        user_search_query.pop(user_id, None)
        user_found_images.pop(user_id, None)
        user_state.pop(user_id, None)
        
        bot.send_message(message.chat.id, 
            "Отправь мне заголовок (текст), который нужно добавить на фото.")

if __name__ == "__main__":
    print("🤖 Telegram бот запущен...")
    print("📱 Откройте Telegram и найдите вашего бота")
    print("⌨️  Используйте команду /start для начала работы")
    
    try:
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        print("Проверьте токен и подключение к интернету") 