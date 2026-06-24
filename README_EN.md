# CManager - Club Management System

[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2%2B-green)](https://www.djangoproject.com/)

[中文](README.md) | [English](README_EN.md)

## 📋 Introduction

**CManager** is a modern club management system developed based on the **Django** framework by the **Student Club Management Center of Shanghai Ocean University**. It aims to provide a comprehensive digital management solution for university clubs, covering core business processes such as club registration, annual review, leadership transition, activity application, reimbursement management, and venue booking.

The system adopts the **Material Design 3 (MD3)** design language, providing a beautiful, unified, and responsive user interface that perfectly adapts to both desktop and mobile access. Core business logic is driven by a custom **Dynamic Form Engine**, enabling flexible configuration of form fields, submission workflows, and review strategies for highly decoupled business logic.

## ✨ Core Features

### 👥 User & Permission System
- **Multi-Role Support**: President, Staff, Admin, Member (main branch); Teacher and Regular User (v1 branch).
- **Fine-Grained Permissions**: RBAC-based permission control with dedicated dashboards for different roles.
- **Personal Center**: Supports avatar upload (auto-cropping), personal information management (QQ / WeChat / gender, etc.), and political status registration.
- **Privacy Protection**: Users can set contact information visibility; supports "Staff-President" association visibility logic (Presidents can view contact details of Staff responsible for their clubs).
- **Member Management**: Supports member join forms, member list viewing, and batch management.
- **QR Code Registration**: Supports generating registration tokens (QR codes) with configurable validity periods and usage limits for easy member onboarding.

### ♻️ Account Lifecycle
- **Auto Inactivation**: Non-admin accounts are automatically marked inactive after lifecycle expiry.
- **Extension Mechanism**: Inactive users can extend and restore active status for another year.
- **Auto Deletion Policy**: Inactive accounts are automatically deleted after 1 year (admins excluded).
- **Admin Controls**: Admins can enable/disable accounts and delete accounts with double confirmation.

### 🏢 Club Lifecycle Management
- **Club Application**: Full-process application and material submission for new club establishment, with automatic club and president creation upon approval.
- **Club Registration**: Club registration process with customizable cycles (yearly/monthly/daily/count-based).
- **Annual Review**: Annual audit process supporting online submission and rejection/modification of various materials (self-assessment forms, constitutions, financial reports, etc.).
- **Leadership Transition**: President transition application and review process, automatically updating club person-in-charge information upon approval.
- **Department Management**: Dynamic configuration of department structure and functions within the management center (supports Highlights for key work).

### 🧩 Dynamic Form & Business Engine
- **Decoupled Architecture**: All business workflows (annual review, registration, application, reimbursement, activity, transition) are driven by a unified dynamic form engine.
- **Flexible Field Configuration**: Supports 9 field types including text, multiline text, number, date, file upload (with multi-file support), radio, checkbox, and more.
- **Cycle-Driven**: Channels can be configured with yearly/monthly/daily or custom numeric cycles, ideal for semester registration and annual review scenarios.
- **Submission Policies**: Supports three submission strategies — repeatable, once total, and once per cycle.
- **Per-Club Toggle**: Admins can enable/disable business channels on a per-club basis.
- **Status Prompts**: Channels can display hint text on the "My Club" dashboard to guide presidents through pending tasks.

### 📅 Activity & Registration
- **Activity Application**: Online submission of activity plans by clubs; approved activities are automatically published to the public activity page.
- **Activity Registration**: Members can browse published activities and register/unregister online (built into the main branch).
- **Reimbursement Management**: Expense reimbursement application, receipt upload (supports Word merge), and approval workflows with amount statistics and history records.

### 🏟️ Venue Booking System
- **Smart Booking**: Online booking for dedicated activity rooms with support for multiple custom rooms and time slots.
- **Conflict Detection**: Built-in time slot conflict detection algorithm to prevent booking overlaps.
- **Fixed Slots**: Supports configuration of fixed opening time slots to standardize venue usage.
- **Calendar View**: Optimized desktop and mobile calendar views for viewing and booking anytime, anywhere.

### 🔍 Audit Center
- **Unified Workbench**: A unified workbench for Staff and Admins to centrally process various applications (activities, reimbursements, registrations, annual reviews, etc.).
- **Multi-Reviewer Approval**: Supports configuring a required approval count — multiple staff/admins can independently review the same submission.
- **Per-Field Rejection**: Supports rejecting individual fields or files; applicants can revise and resubmit (audit records are preserved for each submission attempt).
- **History Records**: Complete audit history archiving, supporting filtering by type and viewing details.

### 📱 Mobile & PWA
- **Responsive Design**: Full-site pages adapted for mobile screens.
- **Bottom Navigation**: Mobile-exclusive bottom navigation bar for easier operation.
- **Touch Optimization**: Interactive experience optimized for touch screens (e.g., popups, sliding lists).
- **PWA Support**: Built-in Service Worker for offline caching and "Add to Home Screen" support.
- **Dark Mode**: Supports light/dark theme switching.

### 🔧 System Administration
- **OOBE Setup Wizard**: First-visit guided setup to create admin accounts and configure basic site info and security parameters.
- **Site Appearance**: Supports custom site logo, favicon, fonts, and other appearance settings.
- **SMTP Configuration**: Database-stored email service configuration, supporting QQ / 163 / Outlook / Gmail and custom SMTP.
- **CSV Batch Import**: Supports batch importing user and club data with transaction handling and error feedback.
- **ZIP Download**: Unified compressed download interface for batch retrieval of submitted materials.
- **Notification API**: Provides a notification count API for real-time pending task reminders.
- **Daily Visit Statistics**: Built-in daily visit tracking.

## 🛠️ Tech Stack

| Category | Technology |
|----------|------------|
| **Backend** | Django 5.2+ (Python 3.12+) |
| **Database** | SQLite (Dev, WAL mode) / MySQL (Prod, via PyMySQL) |
| **Cache** | Redis (django-redis) |
| **Frontend** | Django Templates + Material Design 3 (MD3) |
| **Icons** | Google Material Icons |
| **Image Processing** | Pillow |
| **Document Processing** | python-docx (Word merge), PyMuPDF (PDF processing) |
| **Excel** | openpyxl (import/export) |
| **QR Code** | qrcode[pil] (registration tokens) |
| **PWA** | Service Worker |

## 🚀 Installation & Run

### Requirements

- Python 3.12+
- pip
- (Optional, for production) MySQL, Redis

### Steps

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/shouithub/CManager.git
    cd CManager
    ```

2.  **Create Virtual Environment**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**
    This project provides a `.env.example` file. Copy it to `.env.local` and fill in your configuration:
    ```bash
    # Linux / macOS
    cp .env.example .env.local
    
    # Windows
    copy .env.example .env.local
    ```
    
    Make sure to update the `SECRET_KEY` in `.env.local` with a secure random string.

    Example `.env.local` configuration:
    ```ini
    # Core Security Settings
    SECRET_KEY=your-long-random-secret-key
    DEBUG=True
    ALLOWED_HOSTS=localhost,127.0.0.1
    CSRF_TRUSTED_ORIGINS=http://127.0.0.1,http://localhost

    # Email Service Settings (Optional)
    ADMIN_CONTACT_EMAIL=admin@example.com
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
    EMAIL_HOST=smtp.example.com
    EMAIL_PORT=587
    EMAIL_HOST_USER=no-reply@example.com
    EMAIL_HOST_PASSWORD=your-email-password
    EMAIL_USE_TLS=True
    DEFAULT_FROM_EMAIL=no-reply@example.com

    # Production Security Enhancements (Recommended for Prod)
    SECURE_BROWSER_XSS_FILTER=True
    SECURE_CONTENT_TYPE_NOSNIFF=True
    SESSION_COOKIE_SECURE=False
    CSRF_COOKIE_SECURE=False
    X_FRAME_OPTIONS=DENY
    ```

5.  **Database Migration**
    ```bash
    python manage.py migrate
    ```

    > **Production Tip**: To use MySQL, configure `DATABASE_URL` in `.env.local`; for Redis caching, configure `REDIS_URL`. See `.env.example` for details.
    > The `clubs` app uses a squashed migration now; for a fresh environment, the command above is sufficient.

6.  **First-Run Setup (Recommended)**
    On first visit, the app enters OOBE setup to create an admin account and write local settings safely (not committed to Git).
    If needed, you can still create users manually from CLI.

7.  **Run Development Server**
    ```bash
    python manage.py runserver
    ```

    Visit [http://127.0.0.1:8000](http://127.0.0.1:8000) to start using the system.

8.  **Public Deployment (Nginx Static/Media Serving)**
    In production, it is recommended to let Nginx serve static and media files directly:
    ```nginx
    location /static/ {
        alias /path/to/CManager/staticfiles/;
    }
    location /media/ {
        alias /path/to/CManager/media/;
    }
    ```
    Also run the following during deployment:
    ```bash
    python manage.py collectstatic --noinput
    ```

## 📖 Role Guide

### 👤 President
- **Dashboard**: View club status, notifications, announcements, and pending task prompts.
- **Business Operations**: Submit activity applications, reimbursement applications, annual review materials, transition applications, and club registration via dynamic forms.
- **Venue Booking**: Check available slots and book activity rooms.
- **Info Management**: Update club introduction and view responsible staff contact info.
- **Member Management**: View and manage club member list.

### 🛡️ Staff
- **Audit Center**: Approve various applications for responsible clubs, with per-field review and rejection support.
- **Club Management**: View and manage responsible club information.
- **Statistics**: View club activity levels, financial status, etc.

### ⚙️ Admin
- **System Config**: Manage carousels, department settings, SMTP email services, and site appearance.
- **User Management**: Create users, assign roles, reset passwords, enable/disable accounts, delete accounts with double confirmation, and batch import.
- **Global Control**: Manage dynamic form channels, configure submission cycles, and enable/disable business channels per club.
- **Data Management**: CSV import/export, ZIP download of submitted materials.

## 🌿 Branch Info (v1)

This project includes a `v1` branch that retains the original implementations of features now refactored in the main branch:
- **Extended Roles**: Supports **Teacher** and **Regular User** account types.
- **Legacy Activity Registration**: The v1 branch includes activity registration workflows for regular users (with Teacher approval steps).

> **Note**: The current main branch has migrated core business logic to the dynamic form engine architecture. To reference the legacy fixed-template implementation, please checkout the `v1` branch.

## 📄 License

This project is licensed under the [GPLv2](LICENSE) license.