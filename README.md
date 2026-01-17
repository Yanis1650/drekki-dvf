# Foncier-Express

Analyse foncière DVF (Demande de Valeurs Foncières) avec la méthodologie Mericskay.

## 🚀 Overview

Foncier-Express est une application web permettant de visualiser et d'analyser les transactions immobilières en France. Elle s'appuie sur les données DVF et propose une interface cartographique riche pour explorer les prix, les mutations et les caractéristiques des parcelles.

## 🛠 Tech Stack

- **Backend**: FastAPI, Polars (Lazy processing), DuckDB, PostgreSQL/PostGIS.
- **Frontend**: Vue.js 3, Vite, MapLibre GL JS, Tailwind CSS.
- **Data Engineering**: Polars pour le nettoyage et l'agrégation massive de données.

## 📦 Installation

### Backend
1. Créer un environnement virtuel :
   ```bash
   python -m venv venv
   source venv/bin/activate  # ou venv\Scripts\activate sur Windows
   ```
2. Installer les dépendances :
   ```bash
   pip install -e ".[dev]"
   ```
3. Configurer le fichier `.env` à partir de `.env.example`.

### Frontend
1. Aller dans le dossier frontend :
   ```bash
   cd frontend
   ```
2. Installer les dépendances :
   ```bash
   npm install
   ```
3. Lancer en mode dev :
   ```bash
   npm run dev
   ```

## 🏗 Architecture

Le projet suit les principes de la **Clean Architecture** et du **SOLID** :
- `app/domain`: Modèles de données purs, sans dépendances externes.
- `app/infrastructure`: Implémentations concrètes (Repositories SQLAlchemy/DuckDB).
- `app/api`: Points d'entrée FastAPI.

## 📖 Contribution

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour plus de détails.
