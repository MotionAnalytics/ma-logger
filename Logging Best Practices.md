# **סיכום Best Practices ללוגים בסביבת קונטיינרים (Python)**

מסמך זה מסכם את עקרונות העבודה לכתיבת לוגים בסביבות מבוזרות (K8s, Kestra, Microservices), בדגש על הכנה ל-**OpenTelemetry (OTel)**, מבנה פרויקט רב-קבצים ושימוש בחבילה ייעודית.

## **1\. האסטרטגיה: "OTel-Ready Logging"**

הגישה המומלצת היא לאמץ את **מוסכמות השמות (Semantic Conventions)** של OpenTelemetry כבר עכשיו, גם ללא שימוש ב-SDK המלא שלהם.

### **1.1. היררכיית מזהים (IDs)**

כדי לאפשר מעקב ב-Cluster, אנו משתמשים ב-3 רמות זיהוי:

1. **`trace_id` (Global):** מזהה הבקשה מקצה לקצה.  
2. **`execution_id` (Flow):** מזהה הריצה באורקסטרטור (Kestra).  
3. **`task_id` (Local):** מזהה המשימה/הקונטיינר הספציפי.

## **2\. ארכיטקטורת ה-Root Logger ו"הזרקת" לוגיקה**

אחד האתגרים הוא לגרום לחבילות צד-שלישי (כמו `requests`) או ל-Utils פנימיים שלך (כמו `common-utils`) להוציא לוגים בפורמט JSON עם ה-IDs הנכונים, למרות שהן לא מכירות את הקוד שלך.

### **2.1. איך זה עובד? (The Propagation Magic)**

בפייתון, לוגרים בנויים בעץ היררכי. בראש העץ עומד ה-**Root Logger**.

* **חבילות חיצוניות/Utils:** משתמשים ב-`import logging` ו-`logger.info()`. כברירת מחדל, הן "מבעבעות" (Propagate) את הודעת הלוג למעלה עד ל-Root.  
* **האפליקציה (Main):** מפעילה את `setup_logging()`. פונקציה זו מגדירה את ה-Root Logger ומצמידה אליו את ה-Formatter וה-Filter המיוחדים שלנו.  
* **התוצאה:** ברגע שהגדרת את ה-Root, כל הודעת לוג מכל מקום בפרויקט "נלכדת" על ידי ה-Root ומפורמטת כ-JSON עם כל ה-IDs, בצורה שקופה לחלוטין לקוד שכתב את הלוג.

## **3\. חבילת התשתית: `ma-logger`**

מומלץ לרכז את כל לוגיקת הניטור בחבילה אחת (למשל כחלק מ-`common-utils` או כחבילה עצמאית בשם `ma-logger`).

### **3.1. קוד החבילה (`ma_logger/__init__.py`)**

```
import logging
import json
import os
import sys
import datetime
import functools
import time

# --- רכיב 1: מפרמט JSON תואם OTel ---
class OTelJsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "service.name": os.getenv("SERVICE_NAME", "unknown-service"),
            "log.logger": record.name,
            "log.origin.file.line": record.lineno,
        }
        if hasattr(record, 'otel_ctx'):
            log_record.update(record.otel_ctx)
        if hasattr(record, 'data'):
            log_record["attributes"] = record.data
        if record.exc_info:
            log_record["exception.stacktrace"] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)

# --- רכיב 2: שאיבת קונטקסט אוטומטית ---
class OTelContextFilter(logging.Filter):
    def filter(self, record):
        record.otel_ctx = {
            "trace_id": os.getenv("TRACING_ID") or os.getenv("CORRELATION_ID") or "N/A",
            "execution_id": os.getenv("KESTRA_EXECUTION_ID") or os.getenv("EXECUTION_ID") or "N/A",
            "task_id": os.getenv("KESTRA_TASK_ID") or os.getenv("TASK_ID") or "N/A",
        }
        return True

# --- רכיב 3: פונקציית ה-Setup המרכזית ---
def setup_logging():
    """מגדירה את ה-Root Logger וקובעת לאן יוזרמו הלוגים"""
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        return
        
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    formatter = OTelJsonFormatter()
    ctx_filter = OTelContextFilter()

    # הגדרת הזרמים (Streams)
    # 1. תמיד כותב ל-STDOUT (עבור קונטיינרים/אורקסטרטורים)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(ctx_filter)
    root_logger.addHandler(stdout_handler)

    # 2. כתיבה לקובץ - מופעל רק אם קיים משתנה סביבה LOG_FILE_PATH
    log_file = os.getenv("LOG_FILE_PATH")
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(ctx_filter)
        root_logger.addHandler(file_handler)

# --- רכיב 4: דקורטור לניטור ---
def monitor_task(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            logger.info(f"Task {func.__name__} success", 
                        extra={"data": {"duration": time.perf_counter() - start}})
            return result
        except Exception:
            logger.error(f"Task {func.__name__} failed", exc_info=True)
            raise
    return wrapper
```

## **4\. מדריך עבודה (How-To)**

### **4.1. לכל חבילה פנימית (Utils/Dataclasses)**

**הכלל:** אסור להכיר את `ma-logger`. משתמשים רק בספרייה הסטנדרטית.

```
import logging

logger = logging.getLogger(__name__)

def my_utility_function():
    logger.info("Doing something important") # יפורמט ל-JSON אוטומטית אם בוצע Setup
```

### **4.2. בנקודת הכניסה לאפליקציה (`main.py`)**

כאן מתבצע החיבור.

```
from ma_logger import setup_logging
import logging

# 1. אתחול ה-Root Logger (פעם אחת בתחילת התוכנית)
setup_logging()

# 2. שימוש רגיל
logger = logging.getLogger(__name__)
logger.info("Application Started")
```

### **4.3. הגדרת יעדי הלוגים (Configuration)**

השליטה לאן הלוגים הולכים מתבצעת דרך **משתני סביבה**, ללא שינוי קוד:

* **ריצה בקונטיינר/Kestra:** לא מגדירים כלום (דיפולט ל-STDOUT).  
* **פיתוח מקומי לקובץ:** הגדר `LOG_FILE_PATH=./dev.log`.  
* **שינוי רמת פירוט:** הגדר `LOG_LEVEL=DEBUG`.

## **5\. המעבר ל-OpenTelemetry בעתיד**

בזכות השדה `trace_id` והשימוש ב-STDOUT, המעבר יהיה שקוף:

1. מערכות כמו Grafana Tempo יזהו את ה-`trace_id` בתוך ה-JSON וייצרו תרשים זמנים.  
2. ה-OTel Collector יוכל לאסוף את ה-STDOUT ולהמיר אותו ל-Traces רשמיים.  
3. הקוד ב-Utils וב-Main לא ישתנה, רק ה-Handler בתוך `ma-logger` יוחלף ב-SDK של OTel.

## **6\. דגשים לסביבת Cluster ו-Video**

* **Context Propagation:** בשימוש ב-Parallel Processing, וודאו שה-`trace_id` עובר ב-Headers של ההודעות.  
* **Sampling:** במערכות וידאו מומלץ להשתמש ב-`monitor_task` רק על פעולות כבדות (כמו Inference) ולא על כל פריים, כדי למנוע עומס לוגים.

