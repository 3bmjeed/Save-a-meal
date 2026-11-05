import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()
db = SQLAlchemy()
jwt = JWTManager()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='customer', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    address = db.Column(db.String(240), nullable=False, default='')
    description = db.Column(db.Text, default='')
    opening_hours = db.Column(db.String(120), default='')
    approved = db.Column(db.Boolean, default=False, nullable=False, index=True)

class FoodListing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default='')
    category = db.Column(db.String(60), nullable=False, default='Other', index=True)
    image_url = db.Column(db.String(500), default='')
    original_price = db.Column(db.Integer, nullable=False)  # minor units (e.g. piasters/cents)
    discounted_price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    ingredients = db.Column(db.Text, default='')
    allergens = db.Column(db.Text, default='')
    pickup_deadline = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    restaurant = db.relationship('Restaurant')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(30), default='Pending', nullable=False, index=True)
    total_amount = db.Column(db.Integer, nullable=False)
    pickup_time = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    items = db.relationship('OrderItem', cascade='all, delete-orphan', backref='order')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('food_listing.id'), nullable=False)
    title_snapshot = db.Column(db.String(160), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('food_listing.id'), nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'listing_id', name='uq_favorite_user_listing'),)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('food_listing.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(1000), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'order_id', 'listing_id', name='uq_review_order_listing'),)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    message = db.Column(db.String(500), nullable=False)
    read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class CharityPartner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    organization_name = db.Column(db.String(180), nullable=False)
    approved = db.Column(db.Boolean, default=False, nullable=False)

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('food_listing.id'), nullable=False, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    charity_id = db.Column(db.Integer, db.ForeignKey('charity_partner.id'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    pickup_window = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(30), default='Available', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class AdminAuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(180), nullable=False)
    target_type = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

ROLE_SET = {'customer', 'restaurant', 'admin', 'charity'}

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-only-change-me'),
        JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY', 'dev-jwt-only-change-me'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///save_a_meal.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_SORT_KEYS=False,
    )
    if test_config: app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    origins = os.getenv(
        'FRONTEND_ORIGIN',
        'http://localhost:5173,http://127.0.0.1:5173'
    )

    CORS(
        app,
        resources={
            r'/api/*': {
                'origins': [origin.strip() for origin in origins.split(',')]
            }
        }
    )
    db.init_app(app); jwt.init_app(app)

    @app.errorhandler(400)
    def bad_request(e): return jsonify(error='Bad request', message=str(e)), 400
    @app.errorhandler(404)
    def not_found(e): return jsonify(error='Not found', message='The requested resource was not found.'), 404
    @app.errorhandler(500)
    def server_error(e): db.session.rollback(); return jsonify(error='Server error', message='Something went wrong.'), 500

    def role_required(*roles):
        def decorator(fn):
            @wraps(fn)
            @jwt_required()
            def wrapped(*args, **kwargs):
                user = db.session.get(User, int(get_jwt_identity()))
                if not user or user.role not in roles: return jsonify(error='Forbidden', message='You do not have permission for this action.'), 403
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    def user_json(u): return {'id':u.id,'name':u.name,'email':u.email,'role':u.role}
    def listing_json(x):
        return {'id':x.id,'restaurant_id':x.restaurant_id,'restaurant_name':x.restaurant.name,'address':x.restaurant.address,'title':x.title,'description':x.description,'category':x.category,'image_url':x.image_url,'original_price':x.original_price,'discounted_price':x.discounted_price,'discount_percent':round((1-x.discounted_price/x.original_price)*100) if x.original_price else 0,'quantity':x.quantity,'ingredients':x.ingredients,'allergens':x.allergens,'pickup_deadline':x.pickup_deadline.isoformat(),'active':x.active}
    def notify(user_id, message): db.session.add(Notification(user_id=user_id, message=message))

    @app.get('/api/health')
    def health(): return jsonify(status='ok', app='Happy Meal')

    @app.post('/api/auth/register')
    def register():
        data=request.get_json(silent=True) or {}; name=str(data.get('name','')).strip(); email=str(data.get('email','')).strip().lower(); password=str(data.get('password','')); role=data.get('role','customer')
        if not name or len(name)>100 or '@' not in email or len(password)<8: return jsonify(error='Validation error',message='Provide a name, valid email, and password of at least 8 characters.'),400
        if role not in {'customer','restaurant','charity'}: return jsonify(error='Validation error',message='Invalid role.'),400
        if User.query.filter_by(email=email).first(): return jsonify(error='Conflict',message='An account with this email already exists.'),409
        u=User(name=name,email=email,password_hash=generate_password_hash(password),role=role); db.session.add(u); db.session.flush()
        if role=='restaurant': db.session.add(Restaurant(owner_id=u.id,name=name,approved=False))
        if role=='charity': db.session.add(CharityPartner(user_id=u.id,organization_name=name,approved=False))
        db.session.commit(); token=create_access_token(identity=str(u.id), expires_delta=timedelta(hours=8))
        return jsonify(access_token=token,user=user_json(u)),201

    @app.post('/api/auth/login')
    def login():
        data=request.get_json(silent=True) or {}; email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
        u=User.query.filter_by(email=email).first()
        if not u or not check_password_hash(u.password_hash,password): return jsonify(error='Invalid credentials',message='Email or password is incorrect.'),401
        return jsonify(access_token=create_access_token(identity=str(u.id),expires_delta=timedelta(hours=8)),user=user_json(u))

    @app.get('/api/auth/me')
    @jwt_required()
    def me():
        u=db.session.get(User,int(get_jwt_identity())); return jsonify(user=user_json(u)) if u else (jsonify(error='Not found'),404)

    @app.get('/api/listings')
    def listings():
        q=FoodListing.query.join(Restaurant).filter(FoodListing.active.is_(True),FoodListing.quantity>0,FoodListing.pickup_deadline>datetime.utcnow(),Restaurant.approved.is_(True))
        search=request.args.get('search','').strip()
        if search: q=q.filter(db.or_(FoodListing.title.ilike(f'%{search}%'),Restaurant.name.ilike(f'%{search}%')))
        category=request.args.get('category')
        if category: q=q.filter(FoodListing.category==category)
        try:
            max_price=request.args.get('max_price')
            if max_price is not None: q=q.filter(FoodListing.discounted_price<=int(max_price))
            min_discount=request.args.get('min_discount')
            if min_discount is not None: q=q.filter((FoodListing.original_price-FoodListing.discounted_price)*100>=FoodListing.original_price*int(min_discount))
        except ValueError: return jsonify(error='Validation error',message='Price and discount filters must be numbers.'),400
        return jsonify(items=[listing_json(x) for x in q.order_by(FoodListing.created_at.desc()).all()])

    @app.get('/api/listings/<int:listing_id>')
    def listing_detail(listing_id):
        x=db.session.get(FoodListing,listing_id)
        if not x or not x.active or not x.restaurant.approved: return jsonify(error='Not found',message='This meal is not available.'),404
        return jsonify(item=listing_json(x))

    @app.post('/api/listings')
    @role_required('restaurant')
    def create_listing():
        uid=int(get_jwt_identity()); r=Restaurant.query.filter_by(owner_id=uid).first()
        if not r or not r.approved: return jsonify(error='Approval required',message='Your restaurant must be approved before publishing meals.'),403
        d=request.get_json(silent=True) or {}
        try:
            original=int(d.get('original_price')); discounted=int(d.get('discounted_price')); quantity=int(d.get('quantity')); deadline=datetime.fromisoformat(d.get('pickup_deadline','').replace('Z','+00:00')).replace(tzinfo=None)
        except (ValueError,TypeError): return jsonify(error='Validation error',message='Prices, quantity and pickup deadline are required and must be valid.'),400
        if not d.get('title') or original<=0 or discounted<=0 or discounted>=original or quantity<1 or deadline<=datetime.utcnow(): return jsonify(error='Validation error',message='Check title, prices, quantity and a future pickup deadline. Discounted price must be lower than original price.'),400
        x=FoodListing(restaurant_id=r.id,title=str(d['title'])[:160],description=str(d.get('description',''))[:2000],category=str(d.get('category','Other'))[:60],image_url=str(d.get('image_url',''))[:500],original_price=original,discounted_price=discounted,quantity=quantity,ingredients=str(d.get('ingredients',''))[:1000],allergens=str(d.get('allergens',''))[:500],pickup_deadline=deadline)
        db.session.add(x); db.session.commit(); return jsonify(item=listing_json(x)),201

    @app.patch('/api/listings/<int:listing_id>')
    @role_required('restaurant')
    def update_listing(listing_id):
        x=db.session.get(FoodListing,listing_id); r=Restaurant.query.filter_by(owner_id=int(get_jwt_identity())).first()
        if not x or not r or x.restaurant_id!=r.id: return jsonify(error='Not found',message='Listing not found for this restaurant.'),404
        d=request.get_json(silent=True) or {}
        for key in ('title','description','category','ingredients','allergens'):
            if key in d: setattr(x,key,str(d[key]))
        if 'quantity' in d:
            try:
                if int(d['quantity'])<0: raise ValueError()
                x.quantity=int(d['quantity'])
            except ValueError: return jsonify(error='Validation error',message='Quantity must be zero or greater.'),400
        if 'active' in d: x.active=bool(d['active'])
        db.session.commit(); return jsonify(item=listing_json(x))

    @app.post('/api/orders')
    @role_required('customer')
    def create_order():
        d=request.get_json(silent=True) or {}; items=d.get('items'); pickup=d.get('pickup_time')
        if not isinstance(items,list) or not items: return jsonify(error='Validation error',message='Add at least one meal to your order.'),400
        try: pickup_time=datetime.fromisoformat(pickup.replace('Z','+00:00')).replace(tzinfo=None)
        except (ValueError,AttributeError): return jsonify(error='Validation error',message='Choose a valid pickup time.'),400
        if pickup_time<=datetime.utcnow(): return jsonify(error='Validation error',message='Pickup time must be in the future.'),400
        try:
            with db.session.begin_nested():
                total=0; validated=[]
                for row in items:
                    listing_id=int(row.get('listing_id')); qty=int(row.get('quantity'))
                    if qty<1: raise ValueError('Quantity must be at least one.')
                    x=FoodListing.query.filter_by(id=listing_id,active=True).with_for_update().first()
                    if not x or not x.restaurant.approved or x.pickup_deadline<=datetime.utcnow(): raise ValueError('One of the meals is no longer available.')
                    if pickup_time>x.pickup_deadline: raise ValueError('Pickup time is outside a meal pickup deadline.')
                    if x.quantity<qty: raise ValueError(f'Not enough quantity available for {x.title}.')
                    x.quantity-=qty; total+=x.discounted_price*qty; validated.append((x,qty))
                order=Order(customer_id=int(get_jwt_identity()),total_amount=total,pickup_time=pickup_time,status='Confirmed')
                db.session.add(order); db.session.flush()
                for x,qty in validated:
                    db.session.add(OrderItem(order_id=order.id,listing_id=x.id,title_snapshot=x.title,quantity=qty,unit_price=x.discounted_price))
                    notify(order.customer_id,f'Your reservation for {x.title} is confirmed.')
            db.session.commit()
        except (ValueError,TypeError) as e: db.session.rollback(); return jsonify(error='Reservation failed',message=str(e)),400
        return jsonify(order=order_json(order)),201

    def order_json(o): return {'id':o.id,'status':o.status,'total_amount':o.total_amount,'pickup_time':o.pickup_time.isoformat(),'created_at':o.created_at.isoformat(),'items':[{'listing_id':i.listing_id,'title':i.title_snapshot,'quantity':i.quantity,'unit_price':i.unit_price} for i in o.items]}

    @app.get('/api/orders')
    @jwt_required()
    def get_orders():
        u=db.session.get(User,int(get_jwt_identity()))
        if u.role=='customer': rows=Order.query.filter_by(customer_id=u.id).order_by(Order.created_at.desc()).all()
        elif u.role=='admin': rows=Order.query.order_by(Order.created_at.desc()).all()
        elif u.role=='restaurant':
            r=Restaurant.query.filter_by(owner_id=u.id).first()
            ids=[i.order_id for i in OrderItem.query.join(FoodListing).filter(FoodListing.restaurant_id==r.id).all()] if r else []
            rows=Order.query.filter(Order.id.in_(ids)).order_by(Order.created_at.desc()).all()
        else: return jsonify(error='Forbidden',message='Charity partners do not have customer orders.'),403
        return jsonify(items=[order_json(o) for o in rows])

    @app.patch('/api/orders/<int:order_id>')
    @jwt_required()
    def change_order(order_id):
        o=db.session.get(Order,order_id); u=db.session.get(User,int(get_jwt_identity())); d=request.get_json(silent=True) or {}; status=d.get('status')
        allowed={'Pending','Confirmed','Ready for Pickup','Completed','Cancelled'}
        if not o or status not in allowed: return jsonify(error='Validation error',message='Order or status is invalid.'),400
        owns=o.customer_id==u.id
        if u.role=='restaurant':
            r=Restaurant.query.filter_by(owner_id=u.id).first(); owns=bool(r and any(i.listing_id in [x.id for x in FoodListing.query.filter_by(restaurant_id=r.id).all()] for i in o.items))
        if u.role not in {'admin','restaurant','customer'} or not owns and u.role!='admin': return jsonify(error='Forbidden',message='You cannot update this order.'),403
        if status=='Cancelled':
            if o.status in {'Completed','Cancelled'}: return jsonify(error='Conflict',message='This order cannot be cancelled.'),409
            for item in o.items:
                x=db.session.get(FoodListing,item.listing_id)
                if x and x.pickup_deadline>datetime.utcnow(): x.quantity+=item.quantity
        elif status=='Completed' and u.role=='customer': return jsonify(error='Forbidden',message='Only the restaurant can complete an order.'),403
        o.status=status; notify(o.customer_id,f'Order #{o.id} status changed to {status}.'); db.session.commit(); return jsonify(order=order_json(o))

    @app.get('/api/favorites')
    @role_required('customer')
    def get_favorites():
        rows=Favorite.query.filter_by(user_id=int(get_jwt_identity())).all(); return jsonify(items=[listing_json(db.session.get(FoodListing,f.listing_id)) for f in rows if db.session.get(FoodListing,f.listing_id)])

    @app.post('/api/favorites/<int:listing_id>')
    @role_required('customer')
    def add_favorite(listing_id):
        x=db.session.get(FoodListing,listing_id); uid=int(get_jwt_identity())
        if not x or not x.active: return jsonify(error='Not found',message='Meal not found.'),404
        if not Favorite.query.filter_by(user_id=uid,listing_id=listing_id).first(): db.session.add(Favorite(user_id=uid,listing_id=listing_id)); db.session.commit()
        return jsonify(message='Added to favorites.'),201

    @app.delete('/api/favorites/<int:listing_id>')
    @role_required('customer')
    def remove_favorite(listing_id):
        Favorite.query.filter_by(user_id=int(get_jwt_identity()),listing_id=listing_id).delete(); db.session.commit(); return jsonify(message='Removed from favorites.')

    @app.post('/api/reviews')
    @role_required('customer')
    def create_review():
        d=request.get_json(silent=True) or {}
        try: order_id=int(d.get('order_id')); listing_id=int(d.get('listing_id')); rating=int(d.get('rating'))
        except (TypeError,ValueError): return jsonify(error='Validation error',message='Order, meal and rating are required.'),400
        o=db.session.get(Order,order_id); uid=int(get_jwt_identity())
        if rating not in range(1,6) or not o or o.customer_id!=uid or o.status!='Completed' or not any(i.listing_id==listing_id for i in o.items): return jsonify(error='Forbidden',message='Reviews require your own completed order and a rating from 1 to 5.'),403
        r=Review(user_id=uid,listing_id=listing_id,order_id=order_id,rating=rating,comment=str(d.get('comment',''))[:1000]); db.session.add(r)
        try: db.session.commit()
        except Exception: db.session.rollback(); return jsonify(error='Conflict',message='You have already reviewed this meal for this order.'),409
        return jsonify(message='Review submitted.'),201

    @app.get('/api/notifications')
    @jwt_required()
    def get_notifications():
        rows=Notification.query.filter_by(user_id=int(get_jwt_identity())).order_by(Notification.created_at.desc()).limit(100).all()
        return jsonify(items=[{'id':n.id,'message':n.message,'read':n.read,'created_at':n.created_at.isoformat()} for n in rows])

    @app.patch('/api/notifications/<int:notification_id>')
    @jwt_required()
    def read_notification(notification_id):
        n=Notification.query.filter_by(id=notification_id,user_id=int(get_jwt_identity())).first()
        if not n: return jsonify(error='Not found'),404
        n.read=True; db.session.commit(); return jsonify(message='Notification marked as read.')

    @app.post('/api/donations')
    @role_required('restaurant')
    def create_donation():
        d=request.get_json(silent=True) or {}; r=Restaurant.query.filter_by(owner_id=int(get_jwt_identity()),approved=True).first()
        try: listing_id=int(d.get('listing_id')); qty=int(d.get('quantity')); window=str(d.get('pickup_window','')).strip()
        except (ValueError,TypeError): return jsonify(error='Validation error',message='Listing, quantity and pickup window are required.'),400
        x=db.session.get(FoodListing,listing_id)
        if not r or not x or x.restaurant_id!=r.id or qty<1 or qty>x.quantity or not window: return jsonify(error='Validation error',message='Check the listing, quantity and pickup window.'),400
        x.quantity-=qty; donation=Donation(listing_id=x.id,restaurant_id=r.id,quantity=qty,pickup_window=window); db.session.add(donation); db.session.commit(); return jsonify(id=donation.id,status=donation.status,quantity=donation.quantity),201

    @app.get('/api/donations')
    @jwt_required()
    def get_donations():
        u=db.session.get(User,int(get_jwt_identity()))
        if u.role=='charity':
            cp=CharityPartner.query.filter_by(user_id=u.id,approved=True).first()
            if not cp: return jsonify(error='Approval required',message='Charity partner approval is pending.'),403
            rows=Donation.query.filter(db.or_(Donation.status=='Available',Donation.charity_id==cp.id)).all()
        elif u.role=='restaurant':
            r=Restaurant.query.filter_by(owner_id=u.id).first(); rows=Donation.query.filter_by(restaurant_id=r.id).all() if r else []
        elif u.role=='admin': rows=Donation.query.all()
        else: return jsonify(error='Forbidden'),403
        return jsonify(items=[{'id':x.id,'listing_id':x.listing_id,'meal':db.session.get(FoodListing,x.listing_id).title,'quantity':x.quantity,'pickup_window':x.pickup_window,'status':x.status,'restaurant_id':x.restaurant_id,'charity_id':x.charity_id} for x in rows])

    @app.patch('/api/donations/<int:donation_id>/claim')
    @role_required('charity')
    def claim_donation(donation_id):
        cp=CharityPartner.query.filter_by(user_id=int(get_jwt_identity()),approved=True).first()
        if not cp: return jsonify(error='Approval required',message='Charity partner approval is pending.'),403
        donation=Donation.query.filter_by(id=donation_id,status='Available').with_for_update().first()
        if not donation: return jsonify(error='Conflict',message='This donation is no longer available.'),409
        donation.charity_id=cp.id; donation.status='Requested'; db.session.commit(); return jsonify(message='Donation requested.',status=donation.status)

    @app.patch('/api/donations/<int:donation_id>')
    @jwt_required()
    def update_donation(donation_id):
        d=request.get_json(silent=True) or {}; status=d.get('status'); donation=db.session.get(Donation,donation_id); u=db.session.get(User,int(get_jwt_identity()))
        if not donation or status not in {'Confirmed','Completed'}: return jsonify(error='Validation error',message='Donation or status is invalid.'),400
        r=Restaurant.query.filter_by(owner_id=u.id).first() if u.role=='restaurant' else None
        cp=CharityPartner.query.filter_by(user_id=u.id).first() if u.role=='charity' else None
        if u.role!='admin' and not (r and r.id==donation.restaurant_id) and not (cp and cp.id==donation.charity_id): return jsonify(error='Forbidden'),403
        if status=='Completed' and donation.status not in {'Confirmed','Requested'}: return jsonify(error='Conflict',message='Donation must be requested or confirmed first.'),409
        donation.status=status; db.session.commit(); return jsonify(status=donation.status)

    @app.get('/api/impact')
    def impact():
        completed=Order.query.filter_by(status='Completed').all(); rescued=sum(i.quantity for o in completed for i in o.items); savings=sum((db.session.get(FoodListing,i.listing_id).original_price-i.unit_price)*i.quantity for o in completed for i in o.items if db.session.get(FoodListing,i.listing_id)); donations=Donation.query.filter_by(status='Completed').all()
        return jsonify(completed_orders=len(completed),meals_rescued=rescued,customer_savings=savings,completed_donations=sum(d.quantity for d in donations),active_restaurants=Restaurant.query.filter_by(approved=True).count(),methodology='Meals rescued are quantities from completed orders. Customer savings compare original and discounted unit prices recorded on the order; original listing prices may change later. No carbon savings are claimed.')

    @app.get('/api/dashboard')
    @jwt_required()
    def dashboard():
        u=db.session.get(User,int(get_jwt_identity()))
        if u.role=='admin':
            return jsonify(users=User.query.count(),restaurants=Restaurant.query.count(),pending_restaurants=Restaurant.query.filter_by(approved=False).count(),orders=Order.query.count(),completed_orders=Order.query.filter_by(status='Completed').count(),donations=Donation.query.count())
        if u.role=='restaurant':
            r=Restaurant.query.filter_by(owner_id=u.id).first()
            if not r: return jsonify(error='Not found'),404
            orders=Order.query.join(OrderItem).join(FoodListing).filter(FoodListing.restaurant_id==r.id).distinct().all()
            return jsonify(approved=r.approved,listings=FoodListing.query.filter_by(restaurant_id=r.id).count(),orders=len(orders),completed_orders=sum(o.status=='Completed' for o in orders),revenue=sum(o.total_amount for o in orders if o.status=='Completed'))
        if u.role=='charity':
            cp=CharityPartner.query.filter_by(user_id=u.id).first()
            return jsonify(approved=bool(cp and cp.approved),requested_donations=Donation.query.filter_by(charity_id=cp.id).count() if cp else 0)
        orders=Order.query.filter_by(customer_id=u.id).all(); completed=[o for o in orders if o.status=='Completed']; rescued=sum(i.quantity for o in completed for i in o.items)
        return jsonify(orders=len(orders),completed_orders=len(completed),meals_rescued=rescued,savings=sum((db.session.get(FoodListing,i.listing_id).original_price-i.unit_price)*i.quantity for o in completed for i in o.items if db.session.get(FoodListing,i.listing_id)))

    @app.get('/api/admin/restaurants')
    @role_required('admin')
    def admin_restaurants(): return jsonify(items=[{'id':r.id,'name':r.name,'address':r.address,'approved':r.approved,'owner_id':r.owner_id} for r in Restaurant.query.order_by(Restaurant.id.desc()).all()])

    @app.patch('/api/admin/restaurants/<int:restaurant_id>')
    @role_required('admin')
    def approve_restaurant(restaurant_id):
        r=db.session.get(Restaurant,restaurant_id); d=request.get_json(silent=True) or {}
        if not r: return jsonify(error='Not found'),404
        r.approved=bool(d.get('approved',False)); db.session.add(AdminAuditLog(admin_id=int(get_jwt_identity()),action='restaurant approval changed',target_type='Restaurant',target_id=r.id)); notify(r.owner_id,'Your restaurant approval status is now '+('approved.' if r.approved else 'not approved.')); db.session.commit(); return jsonify(approved=r.approved)

    @app.errorhandler(405)
    def method_not_allowed(e): return jsonify(error='Method not allowed',message='This method is not supported for the endpoint.'),405

    with app.app_context(): db.create_all()
    return app

app=create_app()

if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=os.getenv('FLASK_DEBUG','false').lower()=='true')
