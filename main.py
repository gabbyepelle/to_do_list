from flask import Flask, render_template, redirect, url_for, request, flash
from flask_bootstrap import Bootstrap
from datetime import date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, SubmitField, PasswordField, DateField
from wtforms.validators import DataRequired, URL, Optional
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
Bootstrap(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class TemporaryListItem(db.Model):
    __tablename__ = "display_item"
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.String(100), nullable=True)


class ListItem(db.Model):
    __tablename__ = "list_item"
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey("todo_list.id"))
    item = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.String(100), nullable=True)
    list = relationship("UserList", back_populates="list_items")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    lists = relationship("UserList", back_populates="author")


class UserList(db.Model):
    __tablename__ = "todo_list"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="lists")
    date = db.Column(db.String(250), nullable=False)
    list_items = relationship("ListItem", back_populates="list")


# db.create_all()


# Forms

class AddItem(FlaskForm):
    item = StringField("New Task", validators=[DataRequired()])
    due_date = DateField("Due Date", validators=[Optional()])
    submit = SubmitField("Add Item")


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Sign Me Up!")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Let Me In!")


@app.route("/", methods=["GET", "POST"])
def home():
    form = AddItem()
    if form.validate_on_submit():

        temp_item = TemporaryListItem(
            item=form.item.data,
            due_date=form.due_date.data
        )
        db.session.add(temp_item)
        db.session.commit()
        return redirect(url_for('show_list'))

    return render_template('index.html', form=form)


@app.route("/list", methods=["GET", "POST"])
def show_list():
    form = AddItem()
    if form.validate_on_submit():

        temp_item = TemporaryListItem(
            item=form.item.data,
            due_date=form.due_date.data

        )

        db.session.add(temp_item)
        db.session.commit()
        return redirect(url_for('show_list'))

    all_items = db.session.query(TemporaryListItem).all()

    return render_template('list.html', items=all_items, form=form)


@app.route("/delete", methods=['POST'])
def delete():
    if request.method == "POST":
        checked_items = request.form.getlist("checked")
        if not current_user.is_authenticated:
            for item in checked_items:
                temp_del = TemporaryListItem.query.filter_by(item=item).first()
                db.session.delete(temp_del)
                db.session.commit()
            return redirect(url_for('show_list'))
        else:
            for item in checked_items:
                _del = ListItem.query.filter_by(item=item).first()
                list_id = _del.id
                db.session.delete(_del)
                db.session.commit()

            return redirect(request.referrer)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        if User.query.filter_by(email=form.email.data).first():
            print(User.query.filter_by(email=form.email.data).first())
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User()
        new_user.email = form.email.data
        new_user.password = hash_and_salted_password
        new_user.name = form.name.data
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("show_list"))

    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("That email does not exist. Please try again or Register instead.")
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, password):
            flash("Password incorrect. Please try again.")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('show_list'))

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@login_required
@app.route('/save')
def save_list():
    if not current_user.is_authenticated:
        flash('You must be logged in to save your list')
        return redirect(url_for('login'))
    else:
        items_to_transfer = db.session.query(TemporaryListItem).all()
        for item in items_to_transfer:
            new_item = ListItem(
                item=item.item,
                due_date=item.due_date
            )
            db.session.add(new_item)
            db.session.commit()

        for item in items_to_transfer:
            db.session.delete(item)
            db.session.commit()

        all_items = db.session.query(ListItem).all()

        new_list = UserList(
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
            list_items=all_items
        )

        db.session.add(new_list)
        db.session.commit()
        for item in all_items:
            item.list = new_list
            db.session.commit()

        user_to_update = User.query.get(current_user.id)
        user_to_update.list = new_list
        db.session.commit()
        return redirect(url_for('show_user_lists'))


@login_required
@app.route('/show-lists', methods=['GET', 'POST'])
def show_user_lists():
    return render_template("my-lists.html", current_user=current_user)


@app.route("/edit_list/<int:list_id>", methods=["GET", "POST"])
def edit_list(list_id):
    requested_list = UserList.query.get(list_id)
    form = AddItem()
    if form.validate_on_submit():
        new_item = ListItem(
            item=form.item.data,
            list_id=list_id
        )
        db.session.add(new_item)
        db.session.commit()

        return redirect(url_for('edit_list', list_id=requested_list.id))
    return render_template("edit-list.html", list=requested_list, form=form, current_user=current_user)


@app.route("/delete_user_list/<int:list_id>", methods=["GET", "POST"])
def user_delete(list_id):
    list_to_delete = UserList.query.get(list_id)
    db.session.delete(list_to_delete)
    db.session.commit()
    return redirect(url_for("show_user_lists"))


@app.route("/new-list", methods=["GET", "POST"])
def new_list():
    items_to_clear = db.session.query(TemporaryListItem).all()
    for item in items_to_clear:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)
