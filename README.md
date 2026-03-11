# PlotGod

PlotGod is an AI-powered web application designed for Tabletop RPG (TTRPG) Game Masters. It serves as an ultimate AI assistant, helping you organize your campaigns and generate fresh, engaging ideas for your next sessions.

## 🌟 Features

- **Campaign Management**: Keep track of multiple RPG campaigns at once.
- **Session Tracking**: Log your session transcripts and keep a history of your adventures.
- **Party Members**: Manage your player characters, their stats, and their backstories.
- **AI Session Prep**: Leverage the power of OpenAI's ChatGPT to automatically generate new session ideas, plot hooks, and challenges based on the events of your previous sessions.

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.8+
- An OpenAI API key

### 2. Installation
Clone the repository and install the required dependencies:

```bash
git clone https://github.com/lukerennebach/plotgod.git
cd plotgod
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory and add your OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key_here
```
*(Note: A `.env.backup` is provided as an example structure.)*

### 4. Running the Application
Start the Flask development server:

```bash
python app.py
```
Then, open your browser and navigate to `http://localhost:5000` to start using PlotGod!

## 🛠 Tech Stack
- **Backend**: Python, Flask, SQLite (`data_mgr.py`)
- **Frontend**: HTML/CSS/JS (Jinja2 Templates)
- **AI Integration**: OpenAI API
