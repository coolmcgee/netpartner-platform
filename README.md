# NetPartner Platform

The web platform behind [NetPartner](https://netpartner.site), a New Zealand marketplace that connects content creators with brands for paid campaigns.

Brands post campaigns, creators apply, and every campaign moves through a tracked pipeline from application to verified post and payout. Creators of any size can join, then unlock better deals as they grow their audience and build a reliability rating.

> **Status:** early development. NetPartner currently runs manually while this platform is being built.

## Features

- **Creator and brand accounts** with separate dashboards and per-brand access control
- **Audience tiers** (Starter → Signature) worked out from follower counts, which decide the campaign types a creator can apply for
- **NetPartner Rating (0–100):** starts at 50 and updates automatically, rising for on-time posts and good brand reviews and falling for late or missed posts. Every change is logged as a `RatingEvent`
- **Eligibility rules:** tier, rating, region and a physical-product gate (minimum rating, completed campaigns, engagement and NZ audience share)
- **Region matching:** creators set a home region and can add trips to see campaigns in other regions
- **Campaign tracker:** a board that moves each application through pending → accepted → posted → verified, including missed deadlines
- **Payouts:** a platform fee is added for brands, creators keep 100% of the listed price, and payouts are released after a 7-day view check once earnings pass a minimum
- **Multiple social accounts** per creator (TikTok, Instagram, YouTube Shorts, Facebook)

## Tech stack

- Python and Django 6.1
- SQLite for development
- Django templates with custom CSS
- Deployed on PythonAnywhere

## Project structure

```
netpartner-platform/
├── campaigns/        # Main app: models, views, forms, rating and eligibility logic
│   ├── models.py     # Brand, Creator, SocialAccount, Trip, Campaign, Application, RatingEvent, Review
│   ├── rating.py     # Automatic rating changes
│   ├── eligibility.py
│   └── templates/
└── netpartner/       # Project settings and URLs
```

## Running locally

```bash
git clone https://github.com/coolmcgee/netpartner-platform.git
cd netpartner-platform
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd netpartner-platform
python manage.py migrate
python manage.py seed_demo      # optional demo data
python manage.py createsuperuser
python manage.py runserver
```

Then open http://127.0.0.1:8000.

## About

Built by Oli, a Mechatronics Engineering student at the University of Canterbury and the founder of NetPartner. The platform is developed in Python and Django with the help of AI coding tools.
