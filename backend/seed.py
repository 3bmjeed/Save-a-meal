from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app import app, db, User, Restaurant, FoodListing, CharityPartner


DEMO_LISTINGS = [
    {
        'title': 'Bakery Surprise Box',
        'description': 'A delicious mix of today’s fresh pastries.',
        'category': 'Bakery',
        'image_url': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=900&q=80',
        'original_price': 15000,
        'discounted_price': 7000,
        'quantity': 12,
        'ingredients': 'Wheat flour, butter, sugar, milk',
        'allergens': 'Wheat, milk',
    },
    {
        'title': 'Fresh Sandwich Bundle',
        'description': 'Three freshly prepared sandwiches, packed for pickup.',
        'category': 'Meals',
        'image_url': 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=900&q=80',
        'original_price': 22000,
        'discounted_price': 12000,
        'quantity': 7,
        'ingredients': 'Bread, vegetables, cheese',
        'allergens': 'Wheat, milk',
    },
    {
        'title': 'Cookie Pack',
        'description': 'A pack of soft-baked cookies from today’s batch.',
        'category': 'Dessert',
        'image_url': 'https://images.unsplash.com/photo-1499636136210-6f4ee915583e?auto=format&fit=crop&w=900&q=80',
        'original_price': 9000,
        'discounted_price': 4500,
        'quantity': 15,
        'ingredients': 'Flour, sugar, butter, chocolate',
        'allergens': 'Wheat, milk, soy',
    },
]


def demo_user(email, name, password, role):
    user = User.query.filter_by(email=email).first()
    if user and user.role == role:
        return user
    if user:
        suffix = 1
        while True:
            candidate_email = f'demo-{role}-{suffix}@saveameal.local'
            candidate = User.query.filter_by(email=candidate_email).first()
            if candidate and candidate.role == role:
                return candidate
            if not candidate:
                email = candidate_email
                break
            suffix += 1
    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.session.add(user)
    db.session.flush()
    return user


def seed_demo_data(application=app):
    with application.app_context():
        demo_user('admin@saveameal.local', 'Demo Admin', 'Admin123!', 'admin')
        demo_user('customer@saveameal.local', 'Demo Customer', 'Customer123!', 'customer')
        owner = demo_user(
            'restaurant@saveameal.local',
            'Green Oven',
            'Restaurant123!',
            'restaurant',
        )
        charity_user = demo_user(
            'charity@saveameal.local',
            'Community Food Bank',
            'Charity123!',
            'charity',
        )
        if not CharityPartner.query.filter_by(user_id=charity_user.id).first():
            db.session.add(CharityPartner(
                user_id=charity_user.id,
                organization_name='Community Food Bank',
                approved=True,
            ))

        restaurant = Restaurant.query.filter_by(
            owner_id=owner.id,
            name='Green Oven Bakery',
        ).first()
        if not restaurant:
            restaurant = Restaurant(
                owner_id=owner.id,
                name='Green Oven Bakery',
                address='Assiut, Egypt',
                description='Freshly baked bread and pastries rescued at the end of the day.',
                opening_hours='08:00–22:00',
                approved=True,
            )
            db.session.add(restaurant)
            db.session.flush()

        now = datetime.utcnow()
        available_listing = FoodListing.query.join(Restaurant).filter(
            FoodListing.active.is_(True),
            FoodListing.quantity > 0,
            FoodListing.pickup_deadline > now,
            Restaurant.approved.is_(True),
        ).first()

        refreshed = 0
        if not available_listing and restaurant.approved:
            sample_listings = {
                listing.title: listing
                for listing in FoodListing.query.filter_by(
                    restaurant_id=restaurant.id,
                ).filter(FoodListing.title.in_(
                    [item['title'] for item in DEMO_LISTINGS]
                )).all()
            }
            if sample_listings:
                for listing in sample_listings.values():
                    if listing.active and listing.quantity > 0:
                        listing.pickup_deadline = now + timedelta(days=1)
                        refreshed += 1
            else:
                deadline = now + timedelta(days=1)
                db.session.add_all([
                    FoodListing(restaurant_id=restaurant.id, **item,
                                pickup_deadline=deadline)
                    for item in DEMO_LISTINGS
                ])
                refreshed = len(DEMO_LISTINGS)

        db.session.commit()
        if refreshed:
            print(f'Demo data ready; refreshed {refreshed} demo meal(s).')
        else:
            print('Demo accounts ready; existing available meals were preserved.')
        print('Development-only passwords are documented in README.md.')


if __name__ == '__main__':
    seed_demo_data()
