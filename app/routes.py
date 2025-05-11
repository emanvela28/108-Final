from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from .models import User, Topic, Post, Reply, Vote, Follow, Notification
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
    # Redirect to login if not authenticated, otherwise to the main feed (home_page)
    if not current_user.is_authenticated:
        return redirect(url_for('main.login'))
    return redirect(url_for('main.home_page'))


@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home_page'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.home_page'))
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
@main.route('/my-profile', methods=['GET', 'POST'])
@login_required
def my_profile():
    form = ProfileUpdateForm()
    if form.validate_on_submit() and form.profile_picture.data:
        filename = secure_filename(f"{uuid.uuid4()}_{form.profile_picture.data.filename}")
        upload_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], filename)
        form.profile_picture.data.save(upload_path)
        current_user.profile_picture = filename
        db.session.commit()
        flash('Profile picture updated!', 'success')
        return redirect(url_for('main.my_profile'))
    # Pass current_user as 'user' for consistency with user_profile.html if reusing partials
    return render_template('my_profile.html', user=current_user, form=form, title=f"{current_user.username}'s Profile")


@main.route('/user/<username>')
@login_required
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    filter_type = request.args.get('filter', 'posts')
    is_following = False
    if current_user.is_authenticated and current_user != user:
        is_following = Follow.query.filter_by(user_id=user.id, follower_id=current_user.id).first() is not None

    if filter_type == 'replies':
        content = user.replies.order_by(Reply.timestamp.desc()).all()
    else:  # Default to posts
        content = user.posts.order_by(Post.timestamp.desc()).all()

    return render_template(
        'user_profile.html',
        user=user,
        title=f"{user.username}'s Profile",
        filter=filter_type,
        content=content,
        is_following=is_following
    )


@main.route('/follow/<username>', methods=['POST'])
@login_required
def toggle_follow(username):
    user_to_follow = User.query.filter_by(username=username).first_or_404()
    if user_to_follow == current_user:
        flash("You can't follow yourself.", 'warning')
    else:
        existing_follow = Follow.query.filter_by(user_id=user_to_follow.id, follower_id=current_user.id).first()
        if existing_follow:
            db.session.delete(existing_follow)
            flash(f'You have unfollowed {user_to_follow.username}.', 'info')
        else:
            follow = Follow(user_id=user_to_follow.id, follower_id=current_user.id)
            db.session.add(follow)

            # ✅ Add a notification when followed
            notification = Notification(
                user_id=user_to_follow.id,
                message=f"{current_user.username} started following you."
            )
            db.session.add(notification)

            flash(f'You are now following {user_to_follow.username}!', 'success')

        db.session.commit()
    return redirect(url_for('main.user_profile', username=username))


# ------------------------------ FORUM (FEED & TOPICS) ------------------------------
@main.route('/home')
@login_required
def home_page():
    sort = request.args.get('sort', 'recent')
    if sort == 'popular':
        all_posts = Post.query.outerjoin(Post.votes).group_by(Post.id).order_by(db.func.count(Vote.id).desc()).all()
        page_title = "Most Popular Posts"
    else:
        all_posts = Post.query.order_by(Post.timestamp.desc()).all()
        page_title = "Latest Posts"
    
    return render_template('feed.html', posts=all_posts, title=page_title, current_sort=sort)



@main.route('/topics')
@login_required
def topics_index():
    topics_list = Topic.query.order_by(Topic.name).all()
    return render_template('topics_index.html', topics=topics_list, title="Browse Topics")


# ------------------------------ POSTS & REPLIES ------------------------------
@main.route('/topic/<slug>')
@login_required
def view_topic(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    selected_tag = request.args.get('tag')

    query = topic.posts
    if selected_tag:
        posts = query.filter_by(tag=selected_tag).order_by(Post.timestamp.desc()).all()
    else:
        posts = query.order_by(Post.timestamp.desc()).all()

    all_tags_in_topic_query = db.session.query(Post.tag).filter(Post.topic_id == topic.id, Post.tag != None,
                                                                Post.tag != '').distinct()
    all_tags = sorted([tag_row[0] for tag_row in all_tags_in_topic_query])

    return render_template(
        'topic.html',
        topic=topic,
        title=topic.name,
        posts=posts,
        selected_tag=selected_tag,
        all_tags=all_tags
    )

@main.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    origin = request.args.get('origin', 'topic')
    page_title = post.title
    return render_template('post.html', post=post, title=page_title, origin=origin, Reply=Reply)


@main.route('/topic/<slug>/new', methods=['GET', 'POST'])
@login_required
def create_post(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    TAG_OPTIONS = {
        "cozy-cribs-decor-inspiration": ["Suggestions", "Room Tours", "Aesthetic", "DIY", "Help"],
        "functional-fixes-organization-hacks": ["Tips", "Tools", "Storage", "Tech", "Suggestions"],
        "roommate-realities-advice-support": ["Advice", "Issues", "Good Roommates", "Bad Roommates", "Help"],
        "swap-shop-secondhand-treasures": ["Buy", "Sell", "Swap", "Furniture", "Textbooks"],
        "student-life-local-hotspots": ["Food", "Events", "Housing", "Things to Do", "Advice"]
    }
    form = PostForm()
    # Dynamically set choices for the tag field based on the current topic's slug
    form.tag.choices = [(tag, tag) for tag in
                        TAG_OPTIONS.get(slug, ["General"])]
    if not form.tag.choices:  # Ensure there's always at least one choice
        form.tag.choices = [("General", "General")]

    if form.validate_on_submit():
        filename = None
        if form.image.data:
            file_ext = os.path.splitext(form.image.data.filename)[1].lower()
            if file_ext not in ['.jpg', '.jpeg', '.png', '.gif']:
                flash('Invalid image type. Allowed: jpg, jpeg, png, gif', 'danger')
                return render_template('create_post.html', title=f'New Post in {topic.name}', form=form, topic=topic)

            filename = secure_filename(f"{uuid.uuid4()}_{form.image.data.filename}")
            upload_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], filename)
            form.image.data.save(upload_path)

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
        return redirect(url_for('main.view_post', post_id=new_post.id))  # Redirect to the newly created post
    return render_template('create_post.html', title=f'New Post in {topic.name}', form=form, topic=topic)


@main.route('/post/<int:post_id>/reply', methods=['GET', 'POST'])
@login_required
def create_reply(post_id):
    post = Post.query.get_or_404(post_id)
    form = ReplyForm()
    parent_reply = None

    parent_id = request.args.get('parent')
    if parent_id:
        parent_reply = Reply.query.get(parent_id)

    if form.validate_on_submit():
        reply = Reply(
            content=form.content.data,
            author=current_user,
            post=post,
            parent_reply_id=parent_id
        )
        db.session.add(reply)

        if post.author != current_user:
            notification = Notification(
                user_id=post.author.id,
                message=f"{current_user.username} replied to your post: '{post.title}'"
            )
            db.session.add(notification)

        if parent_reply and parent_reply.author != current_user:
            notification = Notification(
                user_id=parent_reply.author.id,
                message=f"{current_user.username} replied to your comment on '{post.title}'"
            )
            db.session.add(notification)

        db.session.commit()
        flash('Reply posted!', 'success')
        return redirect(url_for('main.view_post', post_id=post.id, _anchor='reply-' + str(reply.id)))

    return render_template(
        'create_reply.html',
        title=f"Reply to '{post.title}'",
        form=form,
        post=post,
        parent_reply=parent_reply
    )


@main.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash("You can only edit your own posts.", "danger")
        return redirect(url_for('main.view_post', post_id=post.id))

    form = PostForm()

    # Dynamically populate tag choices based on topic slug
    TAG_OPTIONS = {
        "cozy-cribs-decor-inspiration": ["Suggestions", "Room Tours", "Aesthetic", "DIY", "Help"],
        "functional-fixes-organization-hacks": ["Tips", "Tools", "Storage", "Tech", "Suggestions"],
        "roommate-realities-advice-support": ["Advice", "Issues", "Good Roommates", "Bad Roommates", "Help"],
        "swap-shop-secondhand-treasures": ["Buy", "Sell", "Swap", "Furniture", "Textbooks"],
        "student-life-local-hotspots": ["Food", "Events", "Housing", "Things to Do", "Advice"]
    }

    topic_slug = post.topic.slug
    tag_choices = TAG_OPTIONS.get(topic_slug, ["General"])
    form.tag.choices = [(tag, tag) for tag in tag_choices]

    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        post.tag = form.tag.data
        post.edited = True
        db.session.commit()
        flash("Post updated successfully.", "success")
        return redirect(url_for('main.view_post', post_id=post.id))

    # Pre-fill form fields for GET request
    form.title.data = post.title
    form.content.data = post.content
    form.tag.data = post.tag

    return render_template('edit_post.html', form=form, post=post, title="Edit Post")


@main.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash("You can only delete your own posts.", "danger")
        return redirect(url_for('main.view_post', post_id=post.id))

    db.session.delete(post)
    db.session.commit()
    flash("Post deleted successfully.", "info")
    return redirect(url_for('main.home_page'))


# ------------------------------ VOTING ------------------------------
@main.route('/vote/post/<int:post_id>/<vote_type>', methods=['POST'])
@login_required
def vote_post(post_id, vote_type):
    post = Post.query.get_or_404(post_id)
    if vote_type not in ['upvote', 'downvote']:
        flash('Invalid vote type.', 'danger')
        return redirect(request.referrer or url_for('main.view_post', post_id=post.id))

    existing_vote = Vote.query.filter_by(user_id=current_user.id, post_id=post.id).first()

    if existing_vote:
        if existing_vote.vote_type == vote_type:
            db.session.delete(existing_vote)
            flash(f'Your {vote_type} was removed.', 'info')
        else:
            existing_vote.vote_type = vote_type
            flash(f'Your vote was changed to a {vote_type}.', 'success')
    else:
        new_vote = Vote(user_id=current_user.id, post_id=post.id, vote_type=vote_type)
        db.session.add(new_vote)

        # Only create a notification if the user is not voting on their own post
        if vote_type == 'upvote' and post.author and post.author != current_user:
            notification = Notification(
                user_id=post.author.id,
                message=f"{current_user.username} upvoted your post: '{post.title}'"
            )
            db.session.add(notification)

        flash(f'You {vote_type}d the post.', 'success')

    db.session.commit()
    return redirect(request.referrer or url_for('main.view_post', post_id=post.id))



@main.route('/vote/reply/<int:reply_id>/<vote_type>', methods=['POST'])
@login_required
def vote_reply(reply_id, vote_type):
    reply = Reply.query.get_or_404(reply_id)
    if vote_type not in ['upvote', 'downvote']:
        flash('Invalid vote type.', 'danger')
        return redirect(request.referrer or url_for('main.view_post', post_id=reply.post_id))

    existing_vote = Vote.query.filter_by(user_id=current_user.id, reply_id=reply.id).first()

    if existing_vote:
        if existing_vote.vote_type == vote_type:
            db.session.delete(existing_vote)
            flash(f'Your {vote_type} was removed from the reply.', 'info')
        else:
            existing_vote.vote_type = vote_type
            flash(f'Your vote on the reply was changed to an {vote_type}.', 'success')
    else:
        new_vote = Vote(user_id=current_user.id, reply_id=reply.id, vote_type=vote_type)
        db.session.add(new_vote)

        if vote_type == 'upvote' and reply.author and reply.author != current_user:
            notification = Notification(
                user_id=reply.author.id,
                message=f"{current_user.username} upvoted your reply on: '{reply.post.title}'"
            )
            db.session.add(notification)

        flash(f'You {vote_type}d the reply.', 'success')


    db.session.commit()
    # Redirect back to the post page, possibly to the specific reply's anchor
    return redirect(url_for('main.view_post', post_id=reply.post_id, _anchor='reply-' + str(reply.id)))

@main.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()

    # Store IDs of notifications that were unread before updating
    unread_ids = [n.id for n in notifications if not n.is_read]

    # Mark all as read
    for n in notifications:
        if not n.is_read:
            n.is_read = True
    db.session.commit()

    return render_template('notifications.html', notifications=notifications, unread_ids=unread_ids, title="Your Notifications")


@main.app_context_processor
def inject_notification_count():
    if current_user.is_authenticated:
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return dict(unread_notifications_count=count)
    return dict(unread_notifications_count=0)

