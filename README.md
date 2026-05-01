# 🏥 AYUSH AI – Intelligent Document Authenticity Analyzer

An AI-powered Flask web application that intelligently analyzes and verifies the authenticity of documents, images, and PDF files using advanced OCR, machine learning, and generative AI. Designed for the AYUSH sector to combat misinformation and ensure document integrity.

---

## 📋 Overview

**AYUSH AI** is a comprehensive document analysis platform built with modern AI technologies. It combines optical character recognition (OCR), rule-based validation, and machine learning to score document authenticity in real-time. Users can upload documents, receive AI-generated insights, and interact with an intelligent chatbot powered by Google Gemini API for deeper analysis and answers.

The application features secure user authentication, cloud-based file storage, and a clean, intuitive interface designed with Ayurveda-inspired aesthetics to create a calming and professional user experience.

---

## ✨ Features

- 📄 **Document Upload** – Upload PDF documents and images (PNG, JPG, etc.)
- 🔍 **OCR Text Extraction** – Automatically extract text using Tesseract OCR engine
- ✅ **Authenticity Scoring** – Analyze document authenticity using ML + rule-based logic
- 🤖 **AI Insights** – Generate intelligent insights and analysis using Google Gemini API
- 💬 **Gemini-Powered Chatbot** – Ask questions and receive intelligent responses about any topic
- 🔐 **User Authentication** – Secure login and signup system
- 📊 **Dashboard** – View analytics, recent uploads, and authenticity scores at a glance
- 📜 **History Tracking** – Keep records of all past uploads and analyses
- 📚 **Research Updates** – Browse latest AYUSH research, yoga, and herbal studies with clickable detail pages
- ☁️ **Cloud Storage** – Secure file storage with Cloudinary integration
- 🎨 **Responsive Modern UI** – Clean, minimal Ayurveda-inspired design with intuitive navigation
- 🌐 **Mobile-Friendly** – Works seamlessly across all devices

---

## 🛠️ Tech Stack

### Frontend
- **HTML5** – Semantic markup
- **CSS3** – Custom styling with Ayurveda-inspired design
- **JavaScript** – Interactive features and DOM manipulation

### Backend
- **Flask** – Lightweight Python web framework
- **Python 3.8+** – Core language

### Artificial Intelligence & Analysis
- **Google Gemini API** – Generative AI for insights and chatbot
- **Tesseract OCR** – Text extraction from images and PDFs
- **Machine Learning** – Rule-based + ML authenticity scoring

### Database & Storage
- **SQLite** – Lightweight database for user data and history
- **Cloudinary** – Cloud storage for uploaded documents
- **Flask-SQLAlchemy** – ORM for database operations

### Authentication & Security
- **Flask-Login** – Session management and user authentication
- **Werkzeug** – Password hashing and security utilities

---

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Tesseract OCR engine
- Git

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/ayush-ai.git
cd ayush-ai
```

### Step 2: Create a Virtual Environment
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Install Tesseract OCR

**Windows:**
1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer and follow the default installation steps
3. Add to system PATH or update in code:
```python
import pytesseract
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

### Step 5: Configure Environment Variables

Create a `.env` file in the project root directory:
```bash
cp .env.example .env
```

Edit `.env` and add your credentials (see section below).

### Step 6: Initialize the Database
```bash
python
>>> from app import db, app
>>> with app.app_context():
>>>     db.create_all()
>>> exit()
```

### Step 7: Run the Application
```bash
python app.py
```

The application will be available at `http://localhost:5000`

---

## 🔑 Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Flask Configuration
SECRET_KEY=your_secret_key_here
FLASK_ENV=development
DEBUG=True

# Database
DATABASE_URL=sqlite:///ayush_db.db

# Tesseract Path (if not in system PATH)
TESSERACT_PATH=/usr/bin/tesseract
```

### Getting API Keys
- **Google Gemini API**: https://ai.google.dev/
- **Cloudinary**: https://cloudinary.com/

---

## � Research Updates Feature

A new **Research Updates** section provides access to curated AYUSH research articles:

- **Browse Articles** – Visit `/updates` to explore the latest research
- **Detailed Views** – Click any article to view full content at `/update/<title>`
- **Responsive Design** – Cards adapt to screen size with smooth interactions
- **AYUSH-Focused Content** – Articles on Yoga, Herbal medicine, Pranayama, and more
- **Navigation** – Easily navigate between research articles and main app

### Using Research Updates
1. Navigate to the **"Research Updates"** link in the main menu
2. Browse available research cards
3. Click any card to view detailed article content
4. Use the back button to return to the research list

---

## �📊 How It Works

### Document Analysis Flow

1. **Upload** – User selects and uploads a PDF or image file
2. **Validation** – File type and size validation
3. **OCR Processing** – Tesseract extracts text from the document
4. **Analysis** – System applies ML model and rule-based checks:
   - Text quality assessment
   - Language patterns
   - Formatting analysis
   - Content validation
5. **Authenticity Score** – Generates a score (0-100) indicating likelihood of authenticity
6. **AI Insights** – Google Gemini API generates detailed analysis and recommendations
7. **Storage** – File and results stored in database; file uploaded to Cloudinary
8. **Dashboard** – Results displayed with visualizations and options to explore further

### Chatbot Interaction

Users can ask questions about their documents or any topic using the Gemini-powered chatbot:
- Context-aware responses
- Document-specific queries
- General knowledge questions
- Analysis clarification

---

## 📁 Project Structure

```
ayush-ai/
├── app.py                    # Main Flask application with all routes
├── analyzer.py              # Document analysis logic
├── chatbot.py               # Gemini chatbot integration
├── dataset.py               # Data models
├── merge_json_to_csv.py     # Data processing utility
├── generate_report.py       # PDF report generator
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variables template
├── static/
│   ├── style.css            # Main stylesheet (Ayurveda-inspired design)
│   └── script.js            # Frontend JavaScript
├── templates/
│   ├── base.html            # Base template with navbar
│   ├── home.html            # Landing page
│   ├── upload.html          # Document upload page
│   ├── dashboard.html       # User dashboard
│   ├── result.html          # Analysis results page
│   ├── history.html         # Upload history
│   ├── review.html          # Document review
│   ├── chatbot.html         # Chatbot interface
│   ├── updates.html         # Research updates list
│   ├── update_detail.html   # Research article detail
│   ├── about.html           # About page
│   ├── login.html           # Login page
│   └── signup.html          # Registration page
├── uploads/                 # Temporary uploaded files
├── project/
│   ├── ayush_dataset.json   # Sample dataset
│   └── dataset.csv          # Dataset CSV
├── AYUSH_AI_Project_Report.pdf  # Generated project report
└── README.md                # This file
```

---

## 🎯 Usage Guide

### Creating an Account
1. Navigate to the signup page
2. Enter email and password
3. Confirm and login

### Uploading a Document
1. Go to **Upload** section
2. Select a PDF or image file
3. Click **Analyze** to process
4. Wait for OCR and analysis to complete

### Viewing Results
1. After analysis, view the authenticity score
2. Read AI-generated insights
3. Explore detailed analysis metrics
4. Use the chatbot to ask follow-up questions

### Using the Chatbot
1. Open the floating chatbot or dedicated page
2. Type your question
3. Receive instant AI-powered responses
4. Continue the conversation for more details

### Tracking History
1. Go to **History** page
2. View all past analyses
3. Click on any entry to review details
4. Download or export results

---

## 📄 Generating Project Report

A comprehensive project report in PDF format can be generated automatically:

```bash
python generate_report.py
```

This creates `AYUSH_AI_Project_Report.pdf` containing:
- Executive summary
- Project overview and objectives
- Complete feature list
- Technology stack details
- Development accomplishments
- Project structure documentation
- Analysis workflow explanation
- Future enhancement roadmap
- Technical highlights
- Installation instructions

---

## 📸 Screenshots

> Insert screenshots here showing:
> - Landing page with Ayurveda-inspired design
> - Document upload interface
> - Authenticity score dashboard
> - Analysis results with AI insights
> - Chatbot conversation interface
> - User history page
> - Research updates section
> - Mobile-responsive views

---

## 🎉 Recent Updates (April 2026)

### Latest Features Added
- ✨ **Ayurveda-Inspired UI Redesign** – Complete frontend redesign with calming color palette and glassmorphism effects
- 📚 **Research Updates Section** – New curated research page with clickable article cards and detail pages
- 🔗 **Interactive Research Cards** – Click any research card to view full article details
- 📄 **Project Report Generator** – Automated PDF report generation with comprehensive documentation
- 🎨 **Enhanced Styling** – Improved responsive design for better mobile experience
- 📊 **Better Navigation** – Streamlined navigation menu with new Research Updates link

### Improvements Made
- Removed verification badges for cleaner UI
- Added detailed article pages with back navigation
- Enhanced card interactivity
- Improved accessibility across all pages
- Better error handling and user feedback

---

## 🔮 Future Improvements

- 🧠 **Enhanced ML Model** – Train custom model for better accuracy
- 🌍 **Multi-Language OCR** – Support for non-English documents
- 🎙️ **Voice Chatbot** – Speak to ask questions instead of typing
- 👥 **Real-Time Collaboration** – Share and analyze documents together
- 📈 **Advanced Analytics** – Detailed reports and trend analysis
- 🔄 **Batch Processing** – Analyze multiple documents at once
- 🌙 **Dark Mode** – Additional theme option
- 📱 **Mobile App** – Native iOS and Android applications
- 🔐 **Enhanced Security** – Two-factor authentication, encryption
- 📊 **Export Reports** – PDF and Excel report generation

---

## 📝 License

This project is created for educational and hackathon purposes. Feel free to use, modify, and distribute under the MIT License.

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 👥 Contributors

- **AYUSH Hackathon Team** – Primary development and design
- **Community** – Contributions and feedback welcome!

For questions, suggestions, or contributions, please open an issue or reach out to the development team.

---

## 📞 Support

If you encounter any issues or have questions:
1. Check the existing issues on GitHub
2. Review the documentation above
3. Ensure all environment variables are correctly configured
4. Verify Tesseract OCR is properly installed
5. Check API key validity

---

**Built with ❤️ for the AYUSH ecosystem**
