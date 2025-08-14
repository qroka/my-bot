import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import glob
try:
    from PIL.Image import Resampling
except ImportError:
    Resampling = None
import time

# Папки
IMG_DIR = 'img'
LOGO_DIR = 'logo'
OUTPUT_DIR = 'output'

# Параметры оформления
CONTAINER_BG = (161, 161, 170, 102)
BLUR_RADIUS = 20

# Создать папку output, если нет
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Получить текст от пользователя
user_text = input('Введите текст для добавления на фото: ')

# Засекаем время начала обработки
start_time = time.time()

# Найти первый логотип
logo_files = glob.glob(os.path.join(LOGO_DIR, '*'))
if not logo_files:
    print('Логотип не найден в папке logo!')
    exit(1)
logo_img = Image.open(logo_files[0]).convert('RGBA')

# Шрифт (используем Inter из папки fonts)
def get_font(size, font_name="Inter-Regular.ttf"):
    try:
        return ImageFont.truetype(os.path.join("fonts", font_name), size)
    except Exception as e:
        print(f"Ошибка загрузки шрифта Inter: {e}")
        return ImageFont.load_default()

# Обработка всех фото
for img_path in glob.glob(os.path.join(IMG_DIR, '*')):
    with Image.open(img_path).convert('RGBA') as base:
        # Привести изображение к квадрату 2160x2160 (cover)
        target_size = 2160
        orig_w, orig_h = base.size
        scale = max(target_size / orig_w, target_size / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        if Resampling:
            resample = Resampling.LANCZOS
        else:
            resample = getattr(Image, 'LANCZOS', None)
            if resample is None:
                resample = getattr(Image, 'BICUBIC', 3)
        base = base.resize((new_w, new_h), resample)
        left = (new_w - target_size) // 2
        top = (new_h - target_size) // 2
        base = base.crop((left, top, left + target_size, top + target_size))
        # Добавить градиент поверх фото
        grad = Image.new('RGBA', base.size, (0, 0, 0, 0))
        grad_draw = ImageDraw.Draw(grad)
        for y in range(base.height):
            # Плавный градиент: 0-50% alpha=0, 50-100% alpha от 0 до 255
            if y < base.height // 2:
                alpha = 0
            else:
                alpha = int(255 * ((y - base.height // 2) / (base.height // 2)))
            alpha = int(alpha * 0.6)  # применяем общую непрозрачность 40%
            grad_draw.line([(0, y), (base.width, y)], fill=(0, 0, 0, alpha))
        base = Image.alpha_composite(base, grad)
        draw = ImageDraw.Draw(base)
        # --- Текст и подпись ---
        main_font = get_font(64)  # крупнее
        sub_font = get_font(48)
        # Размеры основного текста
        try:
            main_bbox = draw.textbbox((0, 0), user_text, font=main_font)
            main_w = main_bbox[2] - main_bbox[0]
            main_h = main_bbox[3] - main_bbox[1]
        except AttributeError:
            main_bbox = main_font.getbbox(user_text)
            main_w = main_bbox[2] - main_bbox[0]
            main_h = main_bbox[3] - main_bbox[1]
        sub_text = 'Сургутский район: бизнес и власть'
        try:
            sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_h = sub_bbox[3] - sub_bbox[1]
        except AttributeError:
            sub_bbox = sub_font.getbbox(sub_text)
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_h = sub_bbox[3] - sub_bbox[1]
        # Паддинги и промежутки
        main_pad = 64
        sub_pad = 40
        between_pad = 96  # расстояние между контейнером и подписью
        margin_x = 96
        # --- Перенос текста по ширине контейнера ---
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            current_line = ''
            for word in words:
                test_line = current_line + (' ' if current_line else '') + word
                w = font.getbbox(test_line)[2] - font.getbbox(test_line)[0]
                if w <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            return lines
        max_text_width = base.width - 2 * margin_x - 2 * main_pad
        lines = wrap_text(user_text, main_font, max_text_width)
        line_height = main_font.getbbox('Ay')[3] - main_font.getbbox('Ay')[1]
        line_spacing = 16
        # Итоговые размеры контейнера
        box_w = base.width - 2 * margin_x
        box_h = int(main_pad * 2 + len(lines) * line_height + (len(lines) - 1) * line_spacing)
        box_x = margin_x
        box_y = int(base.height - box_h - sub_h - between_pad - 32)  # убрано -12, чтобы строго соблюдать between_pad
        # Контейнер с размытым фоном и скруглением 24px
        # Вырезаем область под контейнер
        bg_crop = base.crop((box_x, box_y, box_x + box_w, box_y + box_h))
        # Размываем этот фрагмент
        bg_blur = bg_crop.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
        # Накладываем полупрозрачный цвет
        overlay = Image.new('RGBA', (box_w, box_h), CONTAINER_BG)
        bg_blur = Image.alpha_composite(bg_blur, overlay)
        # Прямоугольная маска без скругления
        mask = Image.new('L', (box_w, box_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rectangle([(0, 0), (box_w, box_h)], fill=255)
        bg_blur.putalpha(mask)
        # Рисуем текст на контейнере
        text_draw = ImageDraw.Draw(bg_blur)
        y = main_pad
        for line in lines:
            x = main_pad
            text_draw.text((x, y), line, font=main_font, fill=(255, 255, 255, 255))
            y += line_height + line_spacing
        # Вставляем контейнер обратно на фото
        base.alpha_composite(bg_blur, (box_x, box_y))
        # Добавляем белую обводку 1px 40% прозрачности
        stroke_layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
        stroke_draw = ImageDraw.Draw(stroke_layer)
        stroke_draw.rectangle([(box_x, box_y), (box_x + box_w - 1, box_y + box_h - 1)], outline=(255, 255, 255, 102), width=1)
        base.alpha_composite(stroke_layer)
        # --- Подпись вне контейнера, ближе к контейнеру ---
        sub_x = margin_x
        # sub_y с фиксированным отступом снизу 48px
        sub_y = base.height - sub_h - 48
        draw = ImageDraw.Draw(base)
        # Добавляем логотип 60x60 перед подписью
        if Resampling:
            logo_small = logo_img.resize((60, 60), Resampling.LANCZOS)
        else:
            logo_small = logo_img.resize((60, 60), 3)  # 3 = BICUBIC
        # Вертикальное выравнивание: логотип по центру строки
        logo_y_sub = int(sub_y + (sub_h - 60) // 2)
        base.alpha_composite(logo_small, (int(sub_x), logo_y_sub))
        # Отступ между логотипом и текстом
        text_offset = 60 + 16
        draw.text((sub_x + text_offset, sub_y), sub_text, font=sub_font, fill=(255, 255, 255, 255))
        # Вставить треугольник с блюром и цветом, как у контейнера
        triangle_size = 600
        # 1. Вырезаем фрагмент фото
        tri_crop = base.crop((base.width - triangle_size, 0, base.width, triangle_size))
        # 2. Размываем
        tri_blur = tri_crop.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
        # 3. Накладываем полупрозрачный цвет
        tri_overlay = Image.new('RGBA', (triangle_size, triangle_size), CONTAINER_BG)
        tri_blur = Image.alpha_composite(tri_blur, tri_overlay)
        # 4. Маска-треугольник
        tri_mask = Image.new('L', (triangle_size, triangle_size), 0)
        tri_mask_draw = ImageDraw.Draw(tri_mask)
        tri_mask_draw.polygon([(triangle_size, 0), (triangle_size, triangle_size), (0, 0)], fill=255)
        tri_blur.putalpha(tri_mask)
        # 5. Вставляем обратно
        base.alpha_composite(tri_blur, (base.width - triangle_size, 0))
        # (удалена обводка треугольника)
        # Вставить логотип в правый верхний угол с маргином 72px
        logo_w, logo_h = logo_img.size
        logo_x = base.width - logo_w - 72
        logo_y = 72
        base.alpha_composite(logo_img, (logo_x, logo_y))
        # Сохранить результат
        out_path = os.path.join(OUTPUT_DIR, os.path.basename(img_path))
        base.convert('RGB').save(out_path)
        print(f'Сохранено: {out_path}')

# После обработки всех файлов выводим время
end_time = time.time()
print(f'Время обработки: {end_time - start_time:.2f} секунд')