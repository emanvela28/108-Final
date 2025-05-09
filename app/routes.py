from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from .models import User, Topic, Post, Reply, Vote, Follow
from .forms import LoginForm, RegisterForm, PostForm, ReplyForm, ProfileUpdateForm
from . import db, login_manager, bcrypt
from werkzeug.utils import secure_filename
import uuid, os

main = Blueprint('main', __name__)

# ------------------------------ USER SESSION ------------------------------
@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home_page'))
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash("Account created! You can now log in.", 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route('/')
def home():
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('main.home_page'))
        else:
            flash('Login failed. Check your credentials.', 'danger')
    return render_template('login.html', title='Login', form=form)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('main.login'))

# ------------------------------ PROFILE & FOLLOW ------------------------------
@main.route('/me')
@login_required
def redirect_to_my_profile():
    return redirect(url_for('main.user_profile', username=current_user.username))

@main.route('/my-profile', methods=['GET', 'POST'])
@login_required
def my_profile():
    form = ProfileUpdateForm()
    if form.validate_on_submit() and form.profile_picture.data:
        filename = secure_filename(f"{uuid.uuid4()}_{form.profile_picture.data.filename}")
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        form.profile_picture.data.save(os.path.join(current_app.root_path, upload_path))
        current_user.profile_picture = filename
        db.session.commit()
        flash('Profile picture updated!', 'success')
        return redirect(url_for('main.my_profile'))

    return render_template('my_profile.html', user=current_user, form=form)



@main.route('/user/<username>')
@login_required
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    filter_type = request.args.get('filter', 'posts')  # 'posts' or 'replies'
    is_following = Follow.query.filter_by(user_id=user.id, follower_id=current_user.id).first()

    if filter_type == 'replies':
        content = user.replies.order_by(Reply.timestamp.desc()).all()
    else:
        content = user.posts.order_by(Post.timestamp.desc()).all()

    return render_template(
        'user_profile.html',
        user=user,
        filter=filter_type,
        content=content,
        is_following=is_following
    )


@main.route('/follow/<username>', methods=['POST'])
@login_required
def toggle_follow(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user == current_user:
        flash("You can't follow yourself.", 'warning')
    else:
        existing = Follow.query.filter_by(user_id=user.id, follower_id=current_user.id).first()
        if existing:
            db.session.delete(existing)
            flash(f'Unfollowed {user.username}', 'info')
        else:
            db.session.add(Follow(user_id=user.id, follower_id=current_user.id))
            flash(f'Now following {user.username}!', 'success')
        db.session.commit()
    return redirect(url_for('main.user_profile', username=username))

# ------------------------------ FORUM ------------------------------
@main.route('/home')
@login_required
def home_page():
    topics = Topic.query.all()
    return render_template('home.html', topics=topics)

@main.route('/topic/<slug>')
@login_required
def view_topic(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    selected_tag = request.args.get('tag')

    if selected_tag:
        posts = topic.posts.filter_by(tag=selected_tag).order_by(Post.timestamp.desc()).all()
    else:
        posts = topic.posts.order_by(Post.timestamp.desc()).all()

    # collect all tags used in this topic
    all_tags = sorted(set(post.tag for post in topic.posts if post.tag))

    return render_template(
        'topic.html',
        topic=topic,
        posts=posts,
        selected_tag=selected_tag,
        all_tags=all_tags
    )


@main.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', post=post)

@main.route('/topic/<slug>/new', methods=['GET', 'POST'])
@login_required
def create_post(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    TAG_OPTIONS = {
        "cozy-cribs-decor-inspiration": ["Suggestions", "Room Tours", "Aesthetic", "DIY", "Help"],
        "functional-fixes-organization-hacks": ["Tips", "Tools", "Storage", "Tech", "Suggestions"],
        "roommate-realities-advice-support": ["Advice", "Issues", "Good Roommates", "Bad Roommates", "Help"],
        "swap-shop-secondhand-treasures": ["Buy", "Sell", "Swap", "Furniture", "Textbooks"],
        "campus-life-local-finds-merced": ["Food", "Events", "Housing", "Things to Do", "Advice"]
    }
    form = PostForm()
    form.tag.choices = [(tag, tag) for tag in TAG_OPTIONS.get(slug, ["General"])]
    if form.validate_on_submit():
        filename = None
        if form.image.data:
            filename = secure_filename(f"{uuid.uuid4()}_{form.image.data.filename}")
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            form.image.data.save(os.path.join(current_app.root_path, upload_path))
        new_post = Post(
            title=form.title.data,
            content=form.content.data,
            tag=form.tag.data,
            author=current_user,
            topic=topic,
            media_url=filename
        )
        db.session.add(new_post)
        db.session.commit()
        flash('Post created successfully!', 'success')
        return redirect(url_for('main.view_topic', slug=slug))
    return render_template('create_post.html', form=form, topic=topic)

@main.route('/post/<int:post_id>/reply', methods=['GET', 'POST'])
@login_required
def create_reply(post_id):
    post = Post.query.get_or_404(post_id)
    form = ReplyForm()
    if form.validate_on_submit():
        reply = Reply(content=form.content.data, author=current_user, post=post)
        db.session.add(reply)
        db.session.commit()
        flash('Reply posted!', 'success')
        return redirect(url_for('main.view_post', post_id=post.id))
    return render_template('create_reply.html', form=form, post=post)

# ------------------------------ VOTING ------------------------------
@main.route('/vote/post/<int:post_id>/<vote_type>', methods=['POST'])
@login_required
def vote_post(post_id, vote_type):
    post = Post.query.get_or_404(post_id)
    existing = Vote.query.filter_by(user_id=current_user.id, post_id=post.id, vote_type=vote_type).first()
    if existing:
        db.session.delete(existing)
        flash(f'{vote_type.capitalize()} removed from post.', 'info')
    else:
        opposite = 'downvote' if vote_type == 'upvote' else 'upvote'
        old = Vote.query.filter_by(user_id=current_user.id, post_id=post.id, vote_type=opposite).first()
        if old:
            db.session.delete(old)
        db.session.add(Vote(user_id=current_user.id, post_id=post.id, vote_type=vote_type))
        flash(f'{vote_type.capitalize()} added to post.', 'success')
    db.session.commit()
    return redirect(url_for('main.view_post', post_id=post.id))

@main.route('/vote/reply/<int:reply_id>/<vote_type>', methods=['POST'])
@login_required
def vote_reply(reply_id, vote_type):
    reply = Reply.query.get_or_404(reply_id)
    existing = Vote.query.filter_by(user_id=current_user.id, reply_id=reply.id, vote_type=vote_type).first()
    if existing:
        db.session.delete(existing)
        flash(f'{vote_type.capitalize()} removed from reply.', 'info')
    else:
        opposite = 'downvote' if vote_type == 'upvote' else 'upvote'
        old = Vote.query.filter_by(user_id=current_user.id, reply_id=reply.id, vote_type=opposite).first()
        if old:
            db.session.delete(old)
        db.session.add(Vote(user_id=current_user.id, reply_id=reply.id, vote_type=vote_type))
        flash(f'{vote_type.capitalize()} added to reply.', 'success')
    db.session.commit()
    return redirect(url_for('main.view_post', post_id=reply.post.id))
