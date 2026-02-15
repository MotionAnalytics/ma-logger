# **מדריך סטנדרטים ו-Pre-commit לפיתוח Python בעידן ה-AI**

מסמך זה מרכז את שכבות ההגנה המומלצות לפרויקט פייתון מודרני, המשלב כתיבת קוד על ידי AI עם בקרה אנושית מקצועית.

## **1\. מפת הדרכים: שכבות ה-Code Standard**

להלן 7 המרכיבים העיקריים של סטנדרט קוד מקצועי והכלים המומלצים עבורם בפייתון.

| סוג / תת סוג | מה זה עושה בקצרה | כלי מומלץ | הערות לשימוש עם AI |
| :---- | :---- | :---- | :---- |
| **Code Formatter** | עיצוב ויזואלי (רווחים, שבירת שורות) | **Black** | הכלי היחיד שמומלץ לתיקון אוטומטי מלא. דטרמיניסטי ובטוח. |
| **Linter (Style & Logic)** | זיהוי "ריחות רעים" וטעויות לוגיות | **Ruff** | מהיר בטירוף. תופס הזיות של AI כמו משתנים לא מוגדרים. |
| **Static Type Checker** | וידוא סוגי נתונים (Types) | **MyPy** | קריטי למניעת באגים ב-Runtime שה-AI עלול להכניס. |
| **Import Sorter** | סידור ה-Imports בראש הקובץ | **isort** / **Ruff** | שומר על סדר אלפביתי וקבוצות יבוא ברורות. |
| **Security Linter** | סריקת פרצות אבטחה | **Bandit** | מוודא שה-AI לא השתמש בפונקציות מסוכנות או סיסמאות קשיחות. |
| **Complexity Checker** | מדידת סיבוכיות הקוד | **Ruff** / **Radon** | מונע מה-AI לייצר פונקציות "מפלצתיות" שבלתי אפשרי לקרוא. |
| **Docstring Checker** | וידוא קיום ואיכות תיעוד | **pydocstyle** / **Ruff** | שומר שה-AI יסביר מה הוא כתב, לטובת המפתח הבא. |

## **2\. קובץ Pre-commit Hook מומלץ**

זהו הקובץ שיבטיח ששום דבר לא נכנס ל-Git בלי לעבור את "מסננת" האיכות. הכלים מוגדרים כך שרק **Black** מתקן, והשאר רק בודקים (**Check**).

שמור את התוכן הבא בקובץ בשם .pre-commit-config.yaml בתיקיית השורש של הפרויקט:

\# .pre-commit-config.yaml  
repos:  
  \# \--- ניקוי כללי \---  
  \- repo: \[https://github.com/pre-commit/pre-commit-hooks\](https://github.com/pre-commit/pre-commit-hooks)  
    rev: v4.5.0  
    hooks:  
      \- id: check-yaml  
      \- id: check-added-large-files  
      \- id: end-of-file-fixer  
      \- id: trailing-whitespace

  \# \--- המיישר (הכלי היחיד שמשנה קוד) \---  
  \- repo: \[https://github.com/psf/black\](https://github.com/psf/black)  
    rev: 24.1.1  
    hooks:  
      \- id: black

  \# \--- הבודק המאוחד (Ruff) \---  
  \- repo: \[https://github.com/astral-sh/ruff-pre-commit\](https://github.com/astral-sh/ruff-pre-commit)  
    rev: v0.2.1  
    hooks:  
      \- id: ruff  
        \# E,F (Flake8), D (pydocstyle), I (isort)  
        \# הוספנו ignore לכמה חוקים חופרים במיוחד  
        args: \[--select, "E,F,D,I", \--ignore, "D100,D104", \--no-fix\]

  \# \--- אבטחה \---  
  \- repo: \[https://github.com/pycqa/bandit\](https://github.com/pycqa/bandit)  
    rev: 1.7.7  
    hooks:  
      \- id: bandit  
        args: \["-ll"\] \# בודק רק מרמת חומרה Medium ומעלה

  \# \--- בדיקת טיפוסים \---  
  \- repo: \[https://github.com/pre-commit/mirrors-mypy\](https://github.com/pre-commit/mirrors-mypy)  
    rev: v1.8.0  
    hooks:  
      \- id: mypy  
        args: \[--ignore-missing-imports\]  
        additional\_dependencies: \[types-requests, types-setuptools\]

## **3\. איך משתיקים בעיות במודע?**

כשאתה מחליט שהכלי "חופר" ואתה רוצה להשאיר את הקוד כפי שהוא, השתמש בשיטות הבאות:

### **א. ברמת השורה (Inline)**

הוסף הערה בסוף השורה הספציפית:

import os  \# noqa: F401  (השתקת Ruff על אימפורט לא בשימוש)  
x: int \= "string"  \# type: ignore  (השתקת MyPy)  
hash\_password(p)  \# nosec  (השתקת Bandit על סיכון אבטחה)

### **ב. ברמת הקובץ**

הוסף הערה בשורה הראשונה של הקובץ כדי להשתיק את כל הקובץ מהכלי:

* **Ruff:** \# ruff: noqa  
* **MyPy:** \# mypy: ignore-errors

### **ג. ברמת הפרויקט (השתקת חוק לצמיתות)**

צור קובץ בשם pyproject.toml והגדר אילו חוקים להתעלם מהם תמיד:

\[tool.ruff\]  
\# חוקים שלא מעניינים אותנו לעולם  
ignore \= \[  
    "D100", \# חסר Docstring בראש מודול  
    "D103", \# חסר Docstring בפונקציות מסוימות  
    "E501", \# שורה ארוכה מדי (סומכים על Black)  
\]

\[tool.mypy\]  
\# הגדרות גלובליות ל-MyPy  
ignore\_missing\_imports \= true

## **פקודות שימושיות**

* **התקנה:** pip install pre-commit && pre-commit install  
* **הרצה ידנית על כל הקבצים:** pre-commit run \--all-files  
* **דילוג על בדיקות (בחירום):** git commit \-m "msg" \--no-verify