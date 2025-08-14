import os
import logging
import glob
from typing import Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
try:
    from PIL.Image import Resampling
except ImportError:
    Resampling = None
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('image_processor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
CONFIG = {
    'target_size': 2160,
    'gradient_height_ratio': 0.4,
    'triangle_size': 600,
    'grid_square_size': 295,  # Размер квадрата сетки
    'grid_line_thickness': 4,  # Толщина линий сетки (в пикселях)
    'grid_opacity_ratio': 0.3,  # Прозрачность сетки (30% от прозрачности градиента)
    'grid_vertical_offset': 75,  # Смещение сетки по вертикали вниз (в пикселях)
    'margins': {'text': 96, 'logo': 71},
    'font_size': 120,
    'line_spacing_ratio': 0.2,
    'max_lines': None,  # Без ограничений по строкам для квадрата
    'gradient_colors': {
        'bottom': (70, 84, 154),        # #46549A (0% прозрачности)
        'bottom_end': (42, 48, 80),     # #2A3050 (100% прозрачности)
        'triangle_start': (42, 48, 80), # #2A3050
        'triangle_end': (70, 84, 154)   # #46549A
    }
}

# Конфигурация для второго изображения (ландшафт) - по центру
CONFIG_LANDSCAPE_CENTER = {
    'target_size': (2310, 1200),  # Ширина x Высота
    'gradient_height_ratio': 0.4,
    'triangle_size': 600,  # Размер треугольника (как в квадратном)
    'grid_square_size': 200,  # Уменьшаем сетку для ландшафта
    'grid_line_thickness': 3,  # Тоньше линии для ландшафта
    'grid_opacity_ratio': 0.3,
    'grid_vertical_offset': 50,  # Меньше смещение для ландшафта
    'margins': {'text': 71, 'logo': 71},  # Новые отступы
    'font_size': 150,  # Больший шрифт
    'line_spacing_ratio': 0.2,
    'gradient_colors': CONFIG['gradient_colors'],  # Те же цвета
    'image_alignment': 'center',  # Выравнивание по центру
    'max_lines': 3,  # Максимальное количество строк для ландшафта
    'logo_size': (180, 180)  # Размер логотипа для ландшафта
}

# Конфигурация для ландшафта - по верху
CONFIG_LANDSCAPE_TOP = {
    'target_size': (2310, 1200),  # Ширина x Высота
    'gradient_height_ratio': 0.4,
    'triangle_size': 600,  # Размер треугольника (как в квадратном)
    'grid_square_size': 200,  # Уменьшаем сетку для ландшафта
    'grid_line_thickness': 3,  # Тоньше линии для ландшафта
    'grid_opacity_ratio': 0.3,
    'grid_vertical_offset': 50,  # Меньше смещение для ландшафта
    'margins': {'text': 71, 'logo': 71},  # Новые отступы
    'font_size': 150,  # Больший шрифт
    'line_spacing_ratio': 0.2,
    'gradient_colors': CONFIG['gradient_colors'],  # Те же цвета
    'image_alignment': 'top',  # Выравнивание по верху
    'max_lines': 3,  # Максимальное количество строк для ландшафта
    'logo_size': (180, 180)  # Размер логотипа для ландшафта
}

# Конфигурация для ландшафта - по низу (оригинальная)
CONFIG_LANDSCAPE_BOTTOM = {
    'target_size': (2310, 1200),  # Ширина x Высота
    'gradient_height_ratio': 0.4,
    'triangle_size': 600,  # Размер треугольника (как в квадратном)
    'grid_square_size': 200,  # Уменьшаем сетку для ландшафта
    'grid_line_thickness': 3,  # Тоньше линии для ландшафта
    'grid_opacity_ratio': 0.3,
    'grid_vertical_offset': 50,  # Меньше смещение для ландшафта
    'margins': {'text': 71, 'logo': 71},  # Новые отступы
    'font_size': 150,  # Больший шрифт
    'line_spacing_ratio': 0.2,
    'gradient_colors': CONFIG['gradient_colors'],  # Те же цвета
    'image_alignment': 'bottom',  # Выравнивание по нижнему краю
    'max_lines': 3,  # Максимальное количество строк для ландшафта
    'logo_size': (180, 180)  # Размер логотипа для ландшафта
}

# Для обратной совместимости
CONFIG_LANDSCAPE = CONFIG_LANDSCAPE_BOTTOM

# Папки
IMG_DIR = 'img'
LOGO_DIR = 'logo'
OUTPUT_DIR = 'output'
FONTS_DIR = 'fonts'

class ImageProcessorError(Exception):
    """Пользовательское исключение для ошибок обработки изображений"""
    pass

def validate_text(text: str) -> str:
    """Валидация введенного текста"""
    if not text or not text.strip():
        raise ValueError("Текст не может быть пустым")
    if len(text.strip()) > 1000:
        raise ValueError("Текст слишком длинный (максимум 1000 символов)")
    return text.strip()

def safe_open_image(path: str) -> Optional[Image.Image]:
    """Безопасное открытие изображения с обработкой ошибок"""
    try:
        return Image.open(path).convert('RGBA')
    except Exception as e:
        logger.error(f"Ошибка открытия изображения {path}: {e}")
        return None

def get_font(size: int, font_name: str = "ACTAY-BOLD.OTF") -> ImageFont.FreeTypeFont:
    """Загрузка шрифта с улучшенной обработкой ошибок"""
    font_path = os.path.join(FONTS_DIR, font_name)
    
    if not os.path.exists(font_path):
        logger.warning(f"Шрифт {font_name} не найден в папке {FONTS_DIR}")
        return ImageFont.load_default()
    
    try:
        return ImageFont.truetype(font_path, size)
    except OSError as e:
        logger.error(f"Ошибка загрузки шрифта {font_name}: {e}")
        return ImageFont.load_default()
    except Exception as e:
        logger.error(f"Неожиданная ошибка при загрузке шрифта: {e}")
        return ImageFont.load_default()

def create_gradient_optimized(width: int, height: int, start_color: Tuple[int, int, int], 
                            end_color: Tuple[int, int, int], reverse: bool = False) -> Image.Image:
    """Оптимизированное создание градиента с использованием numpy"""
    try:
        # Создаем массив градиента
        if reverse:
            # Градиент снизу вверх (плотный вверху, затухает к низу)
            gradient = np.linspace(0, 1, height)[::-1]
        else:
            # Обычный градиент сверху вниз
            gradient = np.linspace(0, 1, height)
        
        # Создаем RGB каналы с правильным broadcasting
        r = np.full((height, width), 0)
        g = np.full((height, width), 0)
        b = np.full((height, width), 0)
        alpha = np.full((height, width), 0)
        
        for i in range(height):
            ratio = gradient[i]
            r[i, :] = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g[i, :] = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b[i, :] = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            alpha[i, :] = int(255 * ratio)
        
        # Объединяем каналы
        gradient_array = np.stack([r, g, b, alpha], axis=-1).astype(np.uint8)
        
        return Image.fromarray(gradient_array)
    
    except Exception as e:
        logger.error(f"Ошибка создания градиента: {e}")
        # Fallback к оригинальному методу
        return create_gradient_fallback(width, height, start_color, end_color, reverse)

def create_gradient_fallback(width: int, height: int, start_color: Tuple[int, int, int], 
                           end_color: Tuple[int, int, int], reverse: bool = False) -> Image.Image:
    """Fallback метод создания градиента (оригинальный)"""
    grad = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    
    for i in range(height):
        if reverse:
            y = height - 1 - i
            alpha = int(255 * (i / height))
        else:
            y = i
            alpha = int(255 * (i / height))
        
        r = int(start_color[0] + (end_color[0] - start_color[0]) * (i / height))
        g = int(start_color[1] + (end_color[1] - start_color[1]) * (i / height))
        b = int(start_color[2] + (end_color[2] - start_color[2]) * (i / height))
        
        grad_draw.line([(0, y), (width, y)], fill=(r, g, b, alpha))
    
    return grad

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = None) -> List[str]:
    """Улучшенный перенос текста с учетом границ шрифта, ограничения строк и принудительным переносом длинных слов"""
    words = text.split()
    lines = []
    current_line = ''
    
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        bbox = font.getbbox(test_line)
        w = bbox[2] - bbox[0]
        
        if w <= max_width:
            current_line = test_line
        else:
            # Если текущая строка не пустая, добавляем её и начинаем новую
            if current_line:
                lines.append(current_line)
                # Проверяем ограничение строк
                if max_lines and len(lines) >= max_lines:
                    break
                current_line = word
            else:
                # Если текущая строка пустая, значит слово само по себе длинное
                # Разбиваем длинное слово на части
                if len(lines) < (max_lines or float('inf')):
                    # Разбиваем слово посимвольно
                    word_parts = []
                    current_part = ''
                    
                    for char in word:
                        test_part = current_part + char
                        bbox = font.getbbox(test_part)
                        part_width = bbox[2] - bbox[0]
                        
                        if part_width <= max_width:
                            current_part = test_part
                        else:
                            if current_part:
                                word_parts.append(current_part)
                                current_part = char
                            else:
                                # Если даже один символ не помещается, добавляем его
                                word_parts.append(char)
                                current_part = ''
                    
                    if current_part:
                        word_parts.append(current_part)
                    
                    # Добавляем части слова в строки
                    for i, part in enumerate(word_parts):
                        if len(lines) < (max_lines or float('inf')):
                            lines.append(part)
                        else:
                            break
                    
                    current_line = ''
                    continue
                else:
                    break
    
    if current_line and (max_lines is None or len(lines) < max_lines):
        lines.append(current_line)
    
    # Если превышено ограничение строк, добавляем многоточие к последней строке
    if max_lines and len(lines) >= max_lines and lines:
        last_line = lines[-1]
        # Проверяем, поместится ли многоточие
        ellipsis = "..."
        test_line = last_line + ellipsis
        bbox = font.getbbox(test_line)
        w = bbox[2] - bbox[0]
        
        if w <= max_width:
            lines[-1] = test_line
        else:
            # Если многоточие не помещается, убираем последние символы
            while last_line and w > max_width:
                last_line = last_line[:-1]
                test_line = last_line + ellipsis
                bbox = font.getbbox(test_line)
                w = bbox[2] - bbox[0]
            lines[-1] = test_line
    
    return lines

def process_single_image_social_only(img_path: str, logo_img: Image.Image, user_text: str) -> bool:
    """Обработка одного изображения только для соцсетей"""
    try:
        with safe_open_image(img_path) as base:
            if base is None:
                return False
            
            # Создаем только изображение для соцсетей
            success = process_image_with_config(base, logo_img, user_text, CONFIG, img_path, "square")
            return success
            
    except Exception as e:
        logger.error(f"Ошибка обработки изображения {img_path}: {e}")
        return False

def process_single_image_investor_only(img_path: str, logo_img: Image.Image, user_text: str) -> bool:
    """Обработка одного изображения только для инвестпортала (создает все варианты)"""
    try:
        with safe_open_image(img_path) as base:
            if base is None:
                return False
            
            # Создаем только варианты для инвестпортала
            success_count = 0
            
            landscape_configs = [
                (CONFIG_LANDSCAPE_CENTER, "landscape_center"),
                (CONFIG_LANDSCAPE_TOP, "landscape_top"),
                (CONFIG_LANDSCAPE_BOTTOM, "landscape_bottom")
            ]
            
            for config, suffix in landscape_configs:
                if process_image_with_config(base, logo_img, user_text, config, img_path, suffix):
                    success_count += 1
            
            return success_count > 0
            
    except Exception as e:
        logger.error(f"Ошибка обработки изображения {img_path}: {e}")
        return False

def process_single_image_investor_only_single(img_path: str, logo_img: Image.Image, user_text: str, landscape_config) -> bool:
    """Обработка одного изображения только для инвестпортала (создает один вариант с выбранной ориентацией)"""
    try:
        with safe_open_image(img_path) as base:
            if base is None:
                return False
            
            # Определяем суффикс на основе выбранной ориентации
            alignment = landscape_config.get('image_alignment', 'bottom')
            suffix = f"landscape_{alignment}"
            print(f"DEBUG: process_single_image_investor_only_single: alignment={alignment}, suffix={suffix}")
            print(f"DEBUG: process_single_image_investor_only_single: landscape_config = {landscape_config}")
            
            # Создаем только один вариант для инвестпортала с выбранной ориентацией
            success = process_image_with_config(base, logo_img, user_text, landscape_config, img_path, suffix)
            return success
            
    except Exception as e:
        logger.error(f"Ошибка обработки изображения {img_path}: {e}")
        return False

def process_single_image_all_orientations(img_path: str, logo_img: Image.Image, user_text: str) -> bool:
    """Обработка одного изображения с созданием всех вариантов ориентации"""
    try:
        with safe_open_image(img_path) as base:
            if base is None:
                return False
            
            # Создаем изображения
            success_count = 0
            
            # Первое изображение (квадрат 2160x2160)
            if process_image_with_config(base, logo_img, user_text, CONFIG, img_path, "square"):
                success_count += 1
            
            # Три варианта ландшафтного изображения
            landscape_configs = [
                (CONFIG_LANDSCAPE_CENTER, "landscape_center"),
                (CONFIG_LANDSCAPE_TOP, "landscape_top"),
                (CONFIG_LANDSCAPE_BOTTOM, "landscape_bottom")
            ]
            
            for config, suffix in landscape_configs:
                if process_image_with_config(base, logo_img, user_text, config, img_path, suffix):
                    success_count += 1
            
            return success_count > 0
            
    except Exception as e:
        logger.error(f"Ошибка обработки изображения {img_path}: {e}")
        return False

def process_single_image(img_path: str, logo_img: Image.Image, user_text: str, landscape_config=None) -> bool:
    """Обработка одного изображения с созданием двух версий (для обратной совместимости)"""
    try:
        with safe_open_image(img_path) as base:
            if base is None:
                return False
            
            # Создаем два изображения
            success_count = 0
            
            # Первое изображение (квадрат 2160x2160)
            if process_image_with_config(base, logo_img, user_text, CONFIG, img_path, "square"):
                success_count += 1
            
            # Второе изображение (ландшафт 2310x1200) с выбранной ориентацией
            landscape_config = landscape_config or CONFIG_LANDSCAPE_BOTTOM
            # Определяем суффикс на основе выбранной ориентации
            alignment = landscape_config.get('image_alignment', 'bottom')
            suffix = f"landscape_{alignment}"
            print(f"DEBUG: process_single_image: alignment={alignment}, suffix={suffix}")
            print(f"DEBUG: process_single_image: landscape_config = {landscape_config}")
            if process_image_with_config(base, logo_img, user_text, landscape_config, img_path, suffix):
                success_count += 1
            
            return success_count > 0
            
    except Exception as e:
        logger.error(f"Ошибка обработки изображения {img_path}: {e}")
        return False

def process_image_with_config(base: Image.Image, logo_img: Image.Image, user_text: str, 
                            config: dict, img_path: str, suffix: str) -> bool:
    """Обработка изображения с заданной конфигурацией"""
    try:
        # Копируем базовое изображение
        img_copy = base.copy()
        
        # Определяем размеры
        if isinstance(config['target_size'], tuple):
            target_width, target_height = config['target_size']
            is_landscape = True
        else:
            target_width = target_height = config['target_size']
            is_landscape = False
        
        # Привести изображение к нужному размеру
        orig_w, orig_h = img_copy.size
        scale = max(target_width / orig_w, target_height / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        # Выбор алгоритма сжатия
        if Resampling:
            resample = Resampling.LANCZOS
        else:
            resample = getattr(Image, 'LANCZOS', None)
            if resample is None:
                resample = getattr(Image, 'BICUBIC', 3)
        
        img_copy = img_copy.resize((new_w, new_h), resample)
        
        # Обрезка и выравнивание
        if is_landscape:
            # Для ландшафта выбираем выравнивание
            left = (new_w - target_width) // 2
            alignment = config.get('image_alignment', 'bottom')
            logger.info(f"Выравнивание ландшафта: {alignment}")
            if alignment == 'top':
                top = 0  # Выравнивание по верху
                logger.info("Применено выравнивание по верху")
            elif alignment == 'center':
                top = (new_h - target_height) // 2  # Выравнивание по центру
                logger.info("Применено выравнивание по центру")
            else:  # bottom
                top = new_h - target_height  # Выравнивание по нижнему краю
                logger.info("Применено выравнивание по низу")
        else:
            # Для квадрата центрируем
            left = (new_w - target_width) // 2
            top = (new_h - target_height) // 2
        
        img_copy = img_copy.crop((left, top, left + target_width, top + target_height))

        # Градиент по нижней части
        grad_height = int(img_copy.height * config['gradient_height_ratio'])
        grad = create_gradient_optimized(
            img_copy.width, grad_height, 
            config['gradient_colors']['bottom'], 
            config['gradient_colors']['bottom_end'],
            reverse=False
        )
        
        # Размещаем градиент внизу
        grad_y = img_copy.height - grad_height
        temp_img = Image.new('RGBA', img_copy.size, (0, 0, 0, 0))
        temp_img.paste(grad, (0, grad_y))
        img_copy = Image.alpha_composite(img_copy, temp_img)

        # Сетка поверх градиента
        grid_square_size = config['grid_square_size']
        grid_overlay = Image.new('RGBA', img_copy.size, (0, 0, 0, 0))
        grid_draw = ImageDraw.Draw(grid_overlay)
        
        # Создаем градиент прозрачности для сетки (белый цвет)
        grid_gradient = create_gradient_optimized(
            img_copy.width, grad_height,
            (255, 255, 255),  # Белый цвет
            (255, 255, 255),  # Белый цвет
            reverse=False
        )
        
        # Вычисляем начальную позицию для центрирования сетки
        grid_start_x = (img_copy.width % grid_square_size) // 2
        grid_start_y = grad_y + (grid_square_size - (img_copy.height - grad_y) % grid_square_size) // 2 + config['grid_vertical_offset']
        
        # Рисуем вертикальные линии сетки
        for x in range(grid_start_x, img_copy.width, grid_square_size):
            if x < img_copy.width:
                for y in range(grad_y, img_copy.height):
                    if y < img_copy.height:
                        grad_pos = (y - grad_y) / grad_height
                        if grad_pos <= 1.0:
                            alpha = int(grid_gradient.getpixel((x, int(grad_pos * grad_height)))[3] * config['grid_opacity_ratio'])
                            for offset in range(config['grid_line_thickness']):
                                if x + offset < img_copy.width:
                                    grid_draw.line([(x + offset, y), (x + offset, y)], fill=(255, 255, 255, alpha))
        
        # Рисуем горизонтальные линии сетки
        for y in range(grid_start_y, img_copy.height, grid_square_size):
            if y < img_copy.height:
                grad_pos = (y - grad_y) / grad_height
                if grad_pos <= 1.0:
                    alpha = int(grid_gradient.getpixel((0, int(grad_pos * grad_height)))[3] * config['grid_opacity_ratio'])
                    for offset in range(config['grid_line_thickness']):
                        if y + offset < img_copy.height:
                            grid_draw.line([(0, y + offset), (img_copy.width, y + offset)], fill=(255, 255, 255, alpha))
        
        # Накладываем сетку на изображение
        img_copy = Image.alpha_composite(img_copy, grid_overlay)

        # Текст пользователя
        draw = ImageDraw.Draw(img_copy)
        margin = config['margins']['text']
        user_font = get_font(config['font_size'])
        max_text_width = img_copy.width - 2 * margin
        
        lines = wrap_text(user_text, user_font, max_text_width, config['max_lines'])
        bbox = user_font.getbbox('Ay')
        line_height = bbox[3] - bbox[1]
        line_spacing = int(line_height * config['line_spacing_ratio'])
        total_text_height = len(lines) * line_height + (len(lines) - 1) * line_spacing
        y = img_copy.height - total_text_height - margin
        
        for line in lines:
            x = margin
            draw.text((x, y), line, font=user_font, fill=(255, 255, 255, 255))
            y += line_height + line_spacing

        # Треугольник с градиентом
        triangle_size = config['triangle_size']
        tri_grad = create_gradient_optimized(
            triangle_size, triangle_size,
            config['gradient_colors']['triangle_start'],
            config['gradient_colors']['triangle_end']
        )
        
        # Создаем маску треугольника
        tri_mask = Image.new('L', (triangle_size, triangle_size), 0)
        tri_mask_draw = ImageDraw.Draw(tri_mask)
        tri_mask_draw.polygon([
            (triangle_size, 0), 
            (triangle_size, triangle_size), 
            (0, 0)
        ], fill=255)
        
        tri_grad.putalpha(tri_mask)
        img_copy.alpha_composite(tri_grad, (img_copy.width - triangle_size, 0))

        # Логотип
        logo_w, logo_h = logo_img.size
        logo_x = img_copy.width - logo_w - config['margins']['logo']
        logo_y = config['margins']['logo']
        
        # Для ландшафтного изображения изменяем размер логотипа
        if 'logo_size' in config and config['logo_size']:
            target_logo_w, target_logo_h = config['logo_size']
            logo_img_resized = logo_img.resize((target_logo_w, target_logo_h), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
            logo_w, logo_h = logo_img_resized.size
            logo_x = img_copy.width - logo_w - config['margins']['logo']
            img_copy.alpha_composite(logo_img_resized, (logo_x, logo_y))
        else:
            img_copy.alpha_composite(logo_img, (logo_x, logo_y))

        # Сохранение результата
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        out_path = os.path.join(OUTPUT_DIR, f"{base_name}_{suffix}.png")
        img_copy.convert('RGB').save(out_path, quality=95, optimize=True)
        logger.info(f'Сохранено: {out_path}')
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обработки изображения с конфигурацией {suffix}: {e}")
        return False

def main():
    """Основная функция программы"""
    try:
        # Создать папку output, если нет
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Проверка существования необходимых папок
        if not os.path.exists(IMG_DIR):
            raise ImageProcessorError(f"Папка {IMG_DIR} не найдена!")
        if not os.path.exists(LOGO_DIR):
            raise ImageProcessorError(f"Папка {LOGO_DIR} не найдена!")
        if not os.path.exists(FONTS_DIR):
            logger.warning(f"Папка {FONTS_DIR} не найдена, будет использован стандартный шрифт")

        # Получить и валидировать текст от пользователя
        user_text = input('Введите текст для добавления на фото: ')
        user_text = validate_text(user_text)
        logger.info(f"Текст для обработки: {user_text}")

        # Засекаем время начала обработки
        start_time = time.time()

        # Найти первый логотип
        logo_files = glob.glob(os.path.join(LOGO_DIR, '*'))
        if not logo_files:
            raise ImageProcessorError('Логотип не найден в папке logo!')
        
        logo_img = safe_open_image(logo_files[0])
        if logo_img is None:
            raise ImageProcessorError('Не удалось загрузить логотип!')

        # Обработка всех фото
        image_files = glob.glob(os.path.join(IMG_DIR, '*'))
        if not image_files:
            raise ImageProcessorError(f'В папке {IMG_DIR} не найдено изображений!')

        logger.info(f"Найдено изображений для обработки: {len(image_files)}")
        
        successful = 0
        failed = 0
        
        for img_path in image_files:
            if process_single_image(img_path, logo_img, user_text):
                successful += 1
            else:
                failed += 1

        # Статистика
        total_time = time.time() - start_time
        logger.info(f"Обработка завершена за {total_time:.2f} секунд")
        logger.info(f"Успешно обработано: {successful}, Ошибок: {failed}")
        
        if successful > 0:
            print(f"\n✅ Обработка завершена успешно!")
            print(f"📊 Обработано изображений: {successful}")
            print(f"⏱️  Время выполнения: {total_time:.2f} сек")
            print(f"📁 Результаты сохранены в папку: {OUTPUT_DIR}")
        else:
            print("❌ Не удалось обработать ни одного изображения")

    except ImageProcessorError as e:
        logger.error(f"Ошибка программы: {e}")
        print(f"❌ Ошибка: {e}")
    except KeyboardInterrupt:
        logger.info("Программа прервана пользователем")
        print("\n⏹️  Программа прервана")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        print(f"❌ Неожиданная ошибка: {e}")

if __name__ == "__main__":
    main()