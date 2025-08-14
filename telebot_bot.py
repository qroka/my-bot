import telebot
import os
import glob
from PIL import Image
import main
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = '8100420576:AAESSCNl4fUM3BhnM0Q2gKH6hmpkI7BltSU'  # Вставьте сюда свой токен
bot = telebot.TeleBot(TOKEN)

user_headers = {}
user_landscape_orientation = {}  # Хранение выбора ориентации для каждого пользователя

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 
        "Привет! Я бот для создания красивых изображений с заголовками.\n\n"
        "📱 Создаю изображения для соцсетей (2160x2160)\n"
        "💼 Создаю изображения для инвестпортала (2310x1200) в 3 вариантах ориентации\n\n"
        "Отправь мне заголовок (текст), который нужно добавить на фото.")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id,
        "📋 Как использовать бота:\n\n"
        "1️⃣ Отправь заголовок (текст)\n"
        "2️⃣ Выбери режим обработки:\n"
        "   • 📱 Только для соцсетей - создаст квадратное изображение\n"
        "   • 📱 Для соцсетей + 💼 Для инвестпортала - выбери ориентацию\n"
        "   • 💼 Только для инвестпортала - выбери ориентацию\n"
        "3️⃣ Отправь фотографию или файл изображения\n"
        "   • Фото - будет сжато Telegram\n"
        "   • Файл - без сжатия, лучшее качество\n"
        "4️⃣ Получи результат:\n"
        "   • 📱 Для соцсетей (2160x2160) как файл\n"
        "   • 💼 3 варианта для инвестпортала (2310x1200):\n"
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
    
    user_headers[message.from_user.id] = message.text
    user_landscape_orientation[message.from_user.id] = 'bottom'  # По умолчанию
    
    bot.send_message(message.chat.id, 
        f"✅ Заголовок сохранен: \"{message.text}\"\n\n"
        "Выбери ориентацию для ландшафтного изображения:",
        reply_markup=create_orientation_keyboard())

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

def process_image_file(message, file_info, user_id):
    """Обработка изображения из файла или фото"""
    try:
        # Скачиваем файл
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Создаем временные папки
        temp_img_dir = f"temp_img_{user_id}"
        temp_logo_dir = f"temp_logo_{user_id}"
        temp_output_dir = f"temp_output_{user_id}"
        
        os.makedirs(temp_img_dir, exist_ok=True)
        os.makedirs(temp_logo_dir, exist_ok=True)
        os.makedirs(temp_output_dir, exist_ok=True)
        
        # Определяем расширение файла
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
    
    # Отправляем сообщение о начале обработки
    processing_msg = bot.send_message(message.chat.id, "🔄 Обрабатываю изображение...")
    
    try:
        # Получаем файл фото
        file_info = bot.get_file(message.photo[-1].file_id)
        if not file_info.file_path:
            bot.send_message(message.chat.id, "❌ Ошибка: не удалось получить путь к файлу фото.")
            return
        
        # Обрабатываем изображение
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
        # Очищаем заголовок пользователя и выбор ориентации
        user_headers.pop(user_id, None)
        user_landscape_orientation.pop(user_id, None)

@bot.message_handler(content_types=['document'])
def get_document(message):
    user_id = message.from_user.id
    if user_id not in user_headers:
        bot.send_message(message.chat.id, "Сначала отправь заголовок!")
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
        # Получаем файл
        file_info = bot.get_file(message.document.file_id)
        if not file_info.file_path:
            bot.send_message(message.chat.id, "❌ Ошибка: не удалось получить путь к файлу.")
            return
        
        # Обрабатываем изображение
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
        # Очищаем заголовок пользователя и выбор ориентации
        user_headers.pop(user_id, None)
        user_landscape_orientation.pop(user_id, None)

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    if not message.text.startswith('/'):
        # Очищаем предыдущие данные пользователя
        user_id = message.from_user.id
        user_headers.pop(user_id, None)
        user_landscape_orientation.pop(user_id, None)
        
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