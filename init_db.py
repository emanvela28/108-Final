from app import create_app, db, bcrypt #adding bcrypt for passwords
import re

app = create_app()

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')

with app.app_context():
    from app.models import User, Topic, Post, Reply, Vote

    db.drop_all()
    db.create_all()

    #hashed test users
    hashed_pw_sally = bcrypt.generate_password_hash('pass123').decode('utf-8')
    student = User(username='sally', password=hashed_pw_sally, role='student')

    hashed_pw_mike = bcrypt.generate_password_hash('teach123').decode('utf-8')
    moderator_mike = User(username='moderator', password=hashed_pw_mike, role='moderator')

    hashed_pw_admin = bcrypt.generate_password_hash('admin123').decode('utf-8')
    admin_user = User(username='admin1', password=hashed_pw_admin, role='admin')

    topics_data = [
        {"name": "Cozy Cribs: Decor & Inspiration",
         "description": "Share your dorm/apartment decor ideas, DIY projects, and room tours!"},
        {"name": "Functional Fixes: Organization & Hacks",
         "description": "Tips for maximizing space, storage solutions, and tech setups."},
        {"name": "Roommate Realities: Advice & Support",
         "description": "Discuss roommate agreements, conflict resolution, and finding compatible housemates."},
        {"name": "Swap Shop & Secondhand Treasures",
         "description": "Buy, sell, or swap furniture, decor, textbooks, and other items."},
        {"name": "Campus Life & Local Finds (Merced)",
         "description": "General chat about student life, events, and cool spots around Merced specific to dorm/apartment living."}
    ]

    created_topics = []
    for topic_data in topics_data:
        slug = slugify(topic_data["name"])
        topic = Topic(name=topic_data["name"], description=topic_data['description'], slug=slug)
        db.session.add(topic)
        created_topics.append(topic)
    db.session.commit()
    print(f"{len(created_topics)} topics created")


    print("Database tables created and initial info added!")