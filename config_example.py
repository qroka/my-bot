# Пример конфигурации для main.py
# Скопируйте этот код в начало main.py для настройки параметров

CONFIG = {
    # Размер выходного изображения (в пикселях)
    'target_size': 2160,
    
    # Высота нижнего градиента (в процентах от высоты изображения)
    'gradient_height_ratio': 0.4,  # 40%
    
    # Размер треугольника в правом верхнем углу
    'triangle_size': 600,
    
    # Параметры сетки
    'grid_square_size': 295,        # Размер квадрата сетки (в пикселях)
    'grid_line_thickness': 4,       # Толщина линий сетки (в пикселях)
    'grid_opacity_ratio': 0.3,      # Прозрачность сетки (30% от прозрачности градиента)
    'grid_vertical_offset': 75,     # Смещение сетки по вертикали вниз (в пикселях)
    
    # Отступы (в пикселях)
    'margins': {
        'text': 96,    # Отступ для текста
        'logo': 71     # Отступ для логотипа
    },
    
    # Параметры текста
    'font_size': 120,              # Размер шрифта
    'line_spacing_ratio': 0.2,     # Межстрочный интервал (20% от высоты строки)
    
    # Цвета градиентов (RGB)
    'gradient_colors': {
        'bottom': (70, 84, 154),        # #46549A (0% прозрачности - плотный)
        'bottom_end': (42, 48, 80),     # #2A3050 (100% прозрачности - затухает)
        'triangle_start': (42, 48, 80), # #2A3050 (начальный цвет треугольника)
        'triangle_end': (70, 84, 154)   # #46549A (конечный цвет треугольника)
    }
}

# Конфигурация для ландшафтного изображения (2310x1200)
CONFIG_LANDSCAPE = {
    'target_size': (2310, 1200),  # Ширина x Высота
    'gradient_height_ratio': 0.4,
    'triangle_size': 600,          # Размер треугольника (как в квадратном)
    'grid_square_size': 200,       # Уменьшенная сетка для ландшафта
    'grid_line_thickness': 3,      # Тоньше линии для ландшафта
    'grid_opacity_ratio': 0.3,
    'grid_vertical_offset': 50,    # Меньше смещение для ландшафта
    'margins': {'text': 71, 'logo': 71},  # Новые отступы
    'font_size': 150,              # Больший шрифт
    'line_spacing_ratio': 0.2,
    'gradient_colors': CONFIG['gradient_colors'],  # Те же цвета
    'image_alignment': 'bottom',   # Выравнивание по нижнему краю
    'max_lines': 3,                # Максимальное количество строк для ландшафта
    'logo_size': (180, 180)        # Размер логотипа для ландшафта
}

# Примеры настройки для разных размеров:
CONFIG_SMALL = {
    'target_size': 1080,           # Меньший размер для экономии места
    'gradient_height_ratio': 0.3,  # Меньший градиент
    'triangle_size': 300,           # Меньший треугольник
    'margins': {'text': 48, 'logo': 36},  # Пропорциональные отступы
    'font_size': 60,               # Меньший шрифт
    'line_spacing_ratio': 0.2,
    'gradient_colors': CONFIG['gradient_colors']
}

CONFIG_LARGE = {
    'target_size': 4320,           # Больший размер для высокого качества
    'gradient_height_ratio': 0.5,  # Больший градиент
    'triangle_size': 800,           # Больший треугольник
    'margins': {'text': 144, 'logo': 108},  # Пропорциональные отступы
    'font_size': 180,              # Больший шрифт
    'line_spacing_ratio': 0.2,
    'gradient_colors': CONFIG['gradient_colors']
}

# Примеры цветовых схем:
CONFIG_DARK_THEME = {
    **CONFIG,
    'gradient_colors': {
        'bottom': (0, 0, 0),              # Черный градиент (плотный)
        'bottom_end': (50, 50, 50),       # Темно-серый (затухает)
        'triangle_start': (50, 50, 50),   # Темно-серый
        'triangle_end': (0, 0, 0)         # Черный
    }
}

CONFIG_BRIGHT_THEME = {
    **CONFIG,
    'gradient_colors': {
        'bottom': (255, 255, 255),        # Белый градиент (плотный)
        'bottom_end': (200, 200, 200),    # Светло-серый (затухает)
        'triangle_start': (200, 200, 200), # Светло-серый
        'triangle_end': (255, 255, 255)   # Белый
    }
}

# Для использования просто замените CONFIG в main.py на одну из этих конфигураций
# Например: CONFIG = CONFIG_SMALL 