# Отчёт о потенциальных утечках памяти

## 1. **КРИТИЧЕСКИЕ УТЕЧКИ**

### 1.1 Бесконечные потоки без корзины (scripts/fetcher.py)
**Файл:** [scripts/fetcher.py](scripts/fetcher.py)  
**Строки:** 30-54, 85-119

```python
def _run_queue(self):
    while True:  # ❌ Бесконечный цикл, работает вечно
        if not self.in_game:
            # ... код ...
            time.sleep(5)
        else:
            time.sleep(2)

def _run_online(self):
    while True:  # ❌ Бесконечный цикл
        # ... код ...
        time.sleep(20)
    else:
        time.sleep(2)

def _run_news(self):
    session = requests.Session()
    while True:  # ❌ Бесконечный цикл, session переиспользуется
        # ... код ...
        time.sleep(120)
```

**Проблема:** Потоки создаются как daemon и работают бесконечно, занимая системные ресурсы.  
**Решение:** Добавить flag для остановки потоков при закрытии приложения.

---

### 1.2 Таймеры без остановки (main.py)
**Файл:** [main.py](main.py#L98-L100)

```python
self.mc_timer = QTimer()
self.mc_timer.timeout.connect(self._check_mc_state)
self.mc_timer.start(2000)  # ❌ Никогда не останавливается
```

**И в `_show_match_notification`:**
```python
self.pulse_timer = QTimer()
self.pulse_timer.timeout.connect(pulse_color)
self.pulse_timer.start(1000)  # ❌ Может быть несколько экземпляров
```

**Проблема:** Таймеры продолжают работать при закрытии приложения.

---

## 2. **РАСТУЩИЕ СТРУКТУРЫ ДАННЫХ (Утечки памяти)**

### 2.1 Словари модов в UI (scripts/ui.py)
**Файл:** [scripts/ui.py](scripts/ui.py#L51-L56)

```python
self.mod_cards = {}
self.mod_buttons = {}
self.mod_labels = {}
self.shaders_data = []
self.resourcepacks_data = []
```

**Проблема:** Эти структуры растут при каждом поиске модов и **никогда не очищаются**, накапливая ссылки на виджеты Qt.

---

### 2.2 Новости в памяти (scripts/ui.py)
**Файл:** [scripts/ui.py](scripts/ui.py#L55)

```python
self.news_data = []  # ❌ Растущий список
```

Каждое обновление добавляет новые элементы, старые остаются.

---

## 3. **НЕЗАКРЫТЫЕ СОЕДИНЕНИЯ И ФАЙЛЫ**

### 3.1 HTTP сессия в requests (scripts/fetcher.py)
**Файл:** [scripts/fetcher.py](scripts/fetcher.py#L76)

```python
def _run_news(self):
    session = requests.Session()  # ❌ Сессия живет вечно
    while True:
        # Переиспользуется сессия
```

**Проблема:** Одна session живет весь цикл жизни потока - может накапливать pool соединений.

---

### 3.2 Открытые файлы в auth.py
**Файл:** [scripts/auth.py](scripts/auth.py#L27-37)

```python
fh_log = open(self.log_file, "rb")
files["file"] = (os.path.basename(self.log_file), fh_log)
file_handles.append(fh_log)
# ... повторяется еще раз ...
file_handles.append(fh_log)  # ❌ Файл добавлен дважды!
```

**Проблема:** Файл может не закрыться или закроется дважды.

---

### 3.3 Discord RPC соединение (main.py)
**Файл:** [main.py](main.py#L635-637)

```python
def update_rpc(self, enable=True):
    if enable:
        if not self.rpc:
            try:
                self.rpc = Presence("1418604142422917330")
                self.rpc.connect()  # ❌ Соединение может не закрыться корректно
```

**Проблема:** При отключении RPC соединение может не закрыться или зависнуть.

---

## 4. **МНОЖЕСТВЕННЫЕ ЭКЗЕМПЛЯРЫ ОБЪЕКТОВ**

### 4.1 Несколько QPropertyAnimation (main.py)
**Файл:** [main.py](main.py#L533-576)

```python
def _show_match_notification(self):
    # ... код ...
    self.anim_in = QPropertyAnimation(...)  # Новые экземпляры
    self.anim_in.start()
    
    # Позже:
    self.anim_out = QPropertyAnimation(...)  # Еще новые
    self.pulse_timer = QTimer()  # И еще
```

**Проблема:** Каждый вызов создает новые объекты. При частых вызовах накапливаются.

---

### 4.2 Worker потоки (scripts/ui.py)
**Файл:** [scripts/ui.py](scripts/ui.py#L57-58)

```python
self.worker = None
self.thread = QThread()  # ❌ Создается но не используется
```

**Проблема:** `self.thread` создается в `__init__` но никогда не используется. Мертвый код.

---

## 5. **СИНТАКСИЧЕСКИЕ ОШИБКИ И УТЕЧКИ**

### 5.1 Файловые handle утечки (main.py)
**Файл:** [main.py](main.py#L918-931)

```python
with open(self.log_file, "rb") as fh_log:
    files["file"] = (os.path.basename(self.log_file), fh_log)
    file_handles.append(fh_log)
    payload = {"embeds": [embed]}
    resp = requests.post(...)
    fh_log.seek(0)
    files["file"] = (os.path.basename(self.log_file), fh_log)  # ❌ Перезапись
    file_handles.append(fh_log)  # ❌ Добавлено дважды
```

---

## 6. **СОБЫТИЯ И СИГНАЛЫ**

### 6.1 Множественные потоки с одним событием (main.py)
**Файл:** [main.py](main.py#L101-108)

```python
if self.discord_rpc:
    threading.Thread(target=self.update_rpc, daemon=True).start()
threading.Thread(target=self.update_mod_info, daemon=True).start()
threading.Thread(target=self.get_updates, daemon=True).start()
threading.Thread(target=self.init_mixer, daemon=True).start()
```

**Проблема:** Множество daemon потоков создаются при инициализации. Нет контроля над ними.

---

## 7. **MEDIA PLAYER И PYGAME**

### 7.1 Pygame mixer инициализация (main.py)
**Файл:** [main.py](main.py#L494-501)

```python
def _show_match_notification(self):
    if self.sound_enabled:
        if not pygame.mixer.get_init():
            pygame.mixer.init()  # Может быть инициализировано несколько раз
        pygame.mixer.music.load(sound_path)
        pygame.mixer.music.play()
```

**Проблема:** Повторная инициализация смесителя может привести к утечкам.

---

## 8. **ВЕРЕТЕНА ЗАПРОСОВ**

### 8.1 Утечка connection pool (scripts/fetcher.py)
**Файл:** [scripts/fetcher.py](scripts/fetcher.py#L85-119)

```python
# Создается одна session на время жизни потока
session = requests.Session()
while True:
    # Повторно используется...
    r = session.get(url, timeout=5)  # Pool может расти
    time.sleep(120)
```

**Проблема:** Connection pool может накапливать соединения.

---

## РЕЗЮМЕ

| № | Проблема | Типаж | Приоритет |
|---|----------|-------|----------|
| 1 | Бесконечные потоки fetcher.py | Логика | 🔴 КРИТИЧНО |
| 2 | mc_timer не останавливается | Таймер | 🔴 КРИТИЧНО |
| 3 | Растущие словари модов | Структуры | 🟠 ВЫСОКИЙ |
| 4 | Новости в памяти | Структуры | 🟠 ВЫСОКИЙ |
| 5 | Discord RPC соединение | Сеть | 🟠 ВЫСОКИЙ |
| 6 | Множественные тобзи файлов | Файлы | 🟠 ВЫСОКИЙ |
| 7 | Mehrfache Animationen | UI | 🟡 СРЕДНИЙ |
| 8 | Неиспользуемый QThread | Эффективность | 🟡 СРЕДНИЙ |

