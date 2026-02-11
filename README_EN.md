# CManager - Club Management System

[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.0%2B-green)](https://www.djangoproject.com/)

[中文](README.md) | [English](README_EN.md)

## 📋 Introduction

**CManager** is a modern club management system developed based on the **Django** framework by the **Student Club Management Center of Shanghai Ocean University**. It aims to provide a comprehensive digital management solution for university clubs, covering core business processes such as club registration, annual review, leadership transition, activity application, reimbursement management, and venue booking.

The system adopts the **Material Design 3 (MD3)** design language, providing a beautiful, unified, and responsive user interface that perfectly adapts to both desktop and mobile access.

## ✨ Core Features

### 👥 User & Permission System
- **Multi-Role Support**: President, Staff, Admin, Teacher (v1 branch), Regular User (v1 branch).
- **Fine-Grained Permissions**: RBAC-based permission control with dedicated dashboards for different roles.
- **Personal Center**: Supports avatar upload (auto-cropping), personal information management, and political status registration.
- **Privacy Protection**: Users can set contact information visibility; supports "Staff-President" association visibility logic (Presidents can view contact details of Staff responsible for their clubs).

### 🏢 Club Lifecycle Management
- **Club Application**: Full-process application and material submission for new club establishment.
- **Club Registration**: Semester-based club registration process supporting custom registration periods.
- **Annual Review**: Annual audit process supporting online submission and rejection/modification of various materials (self-assessment forms, constitutions, financial reports, etc.).
- **Leadership Transition**: President transition application and review process, automatically updating club person-in-charge information.
- **Department Management**: Dynamic configuration of department structure and functions within the management center.

### 📅 Activity & Reimbursement
- **Activity Application**: Online submission of activity plans by clubs with multi-level approval.
- **Reimbursement Management**: Expense reimbursement application, receipt upload, and approval workflows, supporting amount statistics and history records.

### 🏟️ Venue Booking System
- **Smart Booking**: Online booking for dedicated activity rooms (e.g., Room 222).
- **Conflict Detection**: Built-in time slot conflict detection algorithm to prevent booking overlaps.
- **Fixed Slots**: Supports configuration of fixed opening time slots to standardize venue usage.
- **Mobile Adaptation**: Optimized mobile calendar view for viewing and booking anytime, anywhere.

### 🔍 Audit Center
- **Unified Workbench**: A unified workbench for Staff and Admins to centrally process various applications (activities, reimbursements, registrations, annual reviews, etc.).
- **History Records**: Complete audit history archiving, supporting filtering by type and viewing details.
- **Audit Feedback**: Supports rejection opinions and modification suggestions for specific materials.

### 📱 Mobile Adaptation
- **Responsive Design**: Full-site pages adapted for mobile screens.
- **Bottom Navigation**: Mobile-exclusive bottom navigation bar for easier operation.
- **Touch Optimization**: Interactive experience optimized for touch screens (e.g., popups, sliding lists).

## 🛠️ Tech Stack

- **Backend**: Django 5.x (Python 3.13+)
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **Frontend**: Django Templates + Material Design 3 (MD3) + Bootstrap 5 (Partial components)
- **Static Resources**: Google Material Icons
- **Libraries**: Pillow (Image processing), openpyxl (Excel export)

## 🚀 Installation & Run

### Requirements

- Python 3.13+
- pip

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

4.  **Create .env File**
    Create a `.env` file in the project root with the following configuration:
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

6.  **Create Superuser**
    ```bash
    python manage.py createsuperuser
    ```

7.  **Run Development Server**
    ```bash
    python manage.py runserver
    ```

    Visit [http://127.0.0.1:8000](http://127.0.0.1:8000) to start using the system.

## 📖 Role Guide

### 👤 President
- **Dashboard**: View club status, notifications, and announcements.
- **Business Operations**: Submit activity applications, reimbursement applications, annual review materials, and transition applications.
- **Venue Booking**: Check available slots and book activity rooms.
- **Info Management**: Update club introduction and view responsible staff contact info.

### 🛡️ Staff
- **Audit Center**: Approve various applications for responsible clubs.
- **Club Management**: View and manage responsible club information.
- **Statistics**: View club activity levels, financial status, etc.

### ⚙️ Admin
- **System Config**: Manage carousels, department settings, SMTP email services.
- **User Management**: Create users, assign roles, reset passwords.
- **Global Control**: Open/close registration periods, annual review channels, etc.

## 🌿 Branch Info (v1)

This project includes a `v1` branch that retains features simplified in the current main branch:
- **Extended Roles**: Supports **Teacher** and **Regular User** account types.
- **Activity Registration**: Allows regular users to sign up for activities directly through the platform.
- **Process Review**: Includes approval workflows involving the Teacher role.

> **Note**: The current main branch focuses on internal club management and center audit processes. If you need activity registration features for all students, please checkout the `v1` branch.

## 📄 License

This project is licensed under the [GPLv2](LICENSE) license.
