from flask import Flask, redirect, url_for, render_template, flash
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField
from wtforms.validators import DataRequired
from flask_wtf.file import FileField, FileAllowed
import os

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
bcrypt = Bcrypt()

class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and hasattr(current_user, 'role') and current_user.role == 'admin'

    def inaccessible_callback(self, name, **kwargs):
        flash('You do not have permission to access the Admin Panel.', 'danger')
        return redirect(url_for('main.login'))

class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not (current_user.is_authenticated and hasattr(current_user, 'role') and current_user.role == 'admin'):
            flash('You do not have permission to access the Admin Panel.', 'danger')
            return redirect(url_for('main.login'))

        from .models import User, Topic, Post
        user_count = User.query.count()
        topic_count = Topic.query.count()
        post_count = Post.query.count()
        return self.render('admin/index.html',
                           user_count=user_count,
                           topic_count=topic_count,
                           post_count=post_count)

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password')
    role = SelectField('Role', choices=[
        ('student', 'Student'),
        ('moderator', 'Moderator'),
        ('admin', 'Admin')
    ], validators=[DataRequired()])

class UserAdmin(SecureModelView):
    form = UserForm
    column_exclude_list = ['password']
    column_searchable_list = ['username', 'role']
    column_filters = ['role']
    form_columns = ['username', 'password', 'role']

    def on_model_change(self, form, model, is_created):
        if form.password.data:
            if not form.password.data.startswith('$2b$'):
                model.password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        elif not is_created:
            if model.id:
                temp_user = db.session.get(type(model), model.id)
                if temp_user:
                    model.password = temp_user.password
        elif is_created and not form.password.data:
            flash("Password is required for new users.", "error")
            raise ValueError("Password cannot be empty for new users.")

    def delete_model(self, model):
        from .models import Post, Reply
        if Post.query.filter_by(user_id=model.id).first() or \
           Reply.query.filter_by(user_id=model.id).first():
            flash(f"User '{model.username}' has posts or replies and cannot be deleted directly. Please reassign or delete their content first.", "error")
            return False
        return super().delete_model(model)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_super_secret_key_here'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

    # ✅ Upload folder config goes here
    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB limit
    os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    from .models import User, Topic, Post, Reply, Vote, Notification
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    admin = Admin(app, name='Forum Admin Panel', template_mode='bootstrap4', index_view=MyAdminIndexView(url='/admin'))
    admin.add_view(UserAdmin(User, db.session, name="Manage Users"))
    admin.add_view(SecureModelView(Topic, db.session, name="Topics", category="Forum Content"))
    admin.add_view(SecureModelView(Post, db.session, name="Posts", category="Forum Content"))
    admin.add_view(SecureModelView(Reply, db.session, name="Replies", category="Forum Content"))
    admin.add_view(SecureModelView(Vote, db.session, name="Votes", category="Forum Content"))

    return app