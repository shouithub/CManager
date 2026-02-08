# CManager

[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-3.1%2B-green)](https://www.djangoproject.com/)

[中文](README.md) | [English](README_EN.md)

## 🌿 Branch Information (v1)

This project includes a `v1` branch that retains features streamlined from the current version:
- **Extended Roles**: Supports **Teacher** and **Ordinary User** account types.
- **Activity Registration**: Allows ordinary users to sign up for activities directly via the platform.
- **Review Workflow**: Includes approval workflows for teachers.

> **Note**: Due to adjustments in school requirements, these features were removed from the main branch to streamline operations. If you require full activity registration and teacher review capabilities, please checkout the `v1` branch.

## 📋 Project Introduction

**CManager** is a comprehensive club management system developed by the **SHOU Community Management Service Center**, based on the Django framework. It aims to provide efficient and convenient management services for university clubs. The system covers core functions such as club registration, activity application, venue booking, and user management, helping schools better organize and manage colorful club activities.

## ✨ Key Features

- **👥 User Management**: Supports multiple roles (President, Staff, Admin, Teacher, User) with registration, login, and profile management.
- **🏢 Club Management**: Full lifecycle management including club registration application, review, member management, and annual review.
- **📅 Activity Management**: Online activity application, approval process, and activity records.
- **🏟️ Venue Booking**: specialized booking system for Room 222 with automatic conflict detection to ensure orderly venue usage.
- **📢 Notification System**: Announcement publishing and email notification integration.
- **📊 Data Export**: Supports exporting data to Excel format for easy archiving and analysis.
- **🔒 Permission Control**: Secure and reliable access control based on user roles (RBAC).

## 🛠️ Tech Stack

- **Backend**: Django 3.1+ (Python)
- **Database**: SQLite (Dev) / PostgreSQL (Prod recommended)
- **Frontend**: Django Templates + Material Design 3 (MD3) + Bootstrap
- **Tools**: openpyxl (Excel export), Pillow (Image processing)

## 🚀 Installation & Setup

### Prerequisites

- Python 3.8+
- pip

### Steps

1.  **Clone the repository**
    ```bash
    git clone https://github.com/shouithub/CManager.git
    cd CManager
    ```

2.  **Create virtual environment**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Database Migration**
    ```bash
    python manage.py migrate
    ```

5.  **Create Superuser**
    ```bash
    python manage.py createsuperuser
    ```

6.  **Run Development Server**
    ```bash
    python manage.py runserver
    ```

    Visit [http://127.0.0.1:8000](http://127.0.0.1:8000) to start using the system.

## 📖 Usage Guide

### 👤 User Access
- Ordinary users can register accounts.
- Administrators manage user roles and permissions via the admin panel.

### 🏢 Club Operations
- Club presidents submit registration applications.
- Admins/Staff review and approve applications to officially establish clubs.

### 📝 Activity Application
- Clubs submit activity proposals with details.
- Staff review and approve activities.

### 🔑 Venue Booking
- Users apply for Room 222 timeslots.
- System automatically checks for time conflicts.

## 📦 Deployment

### Production (Gunicorn + Nginx)

1.  **Install Gunicorn**
    ```bash
    pip install gunicorn
    ```

2.  **Run Gunicorn**
    ```bash
    gunicorn CManager.wsgi:application --bind 0.0.0.0:8000
    ```

3.  **Configure Nginx** as a reverse proxy.

## 📄 License

This project is licensed under the **GPLv2** License. See the [LICENSE](LICENSE) file for details.

## 📞 Contact

**SHOU Community Management Service Center**
If you have any questions or suggestions, please contact us.
📧 Email: whtrys@outlook.com
