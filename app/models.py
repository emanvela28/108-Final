from . import db
from flask_login import UserMixin
from datetime import datetime

# ----------------------------
# User Model
# ----------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='student')
    profile_picture = db.Column(db.String(255), nullable=True)


    posts = db.relationship('Post', back_populates='author', lazy='dynamic', cascade='all, delete-orphan')
    replies = db.relationship('Reply', back_populates='author', lazy='dynamic', cascade='all, delete-orphan')
    votes = db.relationship('Vote', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')

    followers = db.relationship(
        'Follow',
        foreign_keys='Follow.user_id',
        backref='followed_user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    following = db.relationship(
        'Follow',
        foreign_keys='Follow.follower_id',
        backref='follower_user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<User {self.username}>'

    
class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) 
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'))  

    __table_args__ = (db.UniqueConstraint('user_id', 'follower_id', name='unique_follow'),)

# ----------------------------
# Topic Model
# ----------------------------
class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    posts = db.relationship('Post', back_populates='topic', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Topic {self.name}>'

# ----------------------------
# Post Model (thread/question)
# ----------------------------
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    edited = db.Column(db.Boolean, default=False) 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    media_url = db.Column(db.String(255), nullable=True)
    tag = db.Column(db.String(50), nullable=True)

    author = db.relationship('User', back_populates='posts')
    topic = db.relationship('Topic', back_populates='posts')
    replies = db.relationship('Reply', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')
    votes = db.relationship('Vote', back_populates='post', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def upvotes_count(self):
        return Vote.query.filter_by(post_id=self.id, vote_type='upvote').count()
    @property
    def downvotes_count(self):
        return Vote.query.filter_by(post_id=self.id, vote_type='downvote').count()
    @property
    def score(self):
        return self.upvotes_count - self.downvotes_count
    @property
    def followers_count(self):
        return self.followers.count()

    @property
    def following_count(self):
        return self.following.count()


    def __repr__(self):
        return f'<Post {self.title}>'

# ----------------------------
# Reply Model (answer/comment)
# ----------------------------
class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    media_url = db.Column(db.String(255), nullable=True)

    parent_reply_id = db.Column(db.Integer, db.ForeignKey('reply.id'), nullable=True)

    author = db.relationship('User', back_populates='replies')
    post = db.relationship('Post', back_populates='replies')
    votes = db.relationship('Vote', back_populates='reply', lazy='dynamic', cascade='all, delete-orphan')

    children = db.relationship(
        'Reply',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic'
    )

    @property
    def upvotes_count(self):
        return Vote.query.filter_by(reply_id=self.id, vote_type='upvote').count()
    @property
    def downvotes_count(self):
        return Vote.query.filter_by(reply_id=self.id, vote_type='downvote').count()
    @property
    def score(self):
        return self.upvotes_count - self.downvotes_count

    def __repr__(self):
        return f'<Reply {self.id} to Post {self.post_id}>'

# ----------------------------
# Vote Model (up/down-votes)
# ----------------------------
class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    reply_id = db.Column(db.Integer, db.ForeignKey('reply.id'), nullable=True)
    vote_type = db.Column(db.String(10), nullable=False)

    user = db.relationship('User', back_populates='votes')
    post = db.relationship('Post', back_populates='votes')
    reply = db.relationship('Reply', back_populates='votes')

    # Ensures each user can only have one type of vote (up OR down) per item.
    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', 'vote_type', name='uq_user_post_vote_type'),
        db.UniqueConstraint('user_id', 'reply_id', 'vote_type', name='uq_user_reply_vote_type'),
    )

    def __repr__(self):
        item_id = self.post_id if self.post_id else self.reply_id
        item_type = "Post" if self.post_id else "Reply"

        return f'<Vote {self.vote_type} by User {self.user_id} for {item_type} {item_id}>'
    
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='notifications')

    def __repr__(self):
        return f"<Notification to User {self.user_id}: {self.message}>"
    
