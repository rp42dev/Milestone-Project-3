from flask import (Flask, flash, render_template,
        redirect, request, session, url_for, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
from cloudinary.utils import cloudinary_url
from cloudinary.uploader import upload
from bson.objectid import ObjectId
from datetime import datetime
from app import app, mongo
import cloudinary.api
import requests

# dd/mm/YY H:M:S format
now = datetime.now().strftime("%d-%m-%y, %H:%M:%S")


@app.route('/')
@app.route('/index')
def index():
    # Find existing post by id and get category
    digital_art = mongo.db.posts.find({"category_name": "digital_art"}).limit(3)
    painting = mongo.db.posts.find({"category_name": "paintings"}).limit(3)
    images = mongo.db.posts.find({"category_name": "images"}).limit(3)
    return render_template(
        'index.html', digital_art=digital_art, painting=painting, images=images, title="home")


@app.route("/register", methods=["GET", "POST"])
def register():

    """
    Register new users
    Hash the passwords and
    add to the mongo DB user collection
    """

    if request.method == "POST":
        # check username exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})
        if existing_user:
            flash("Username already exists")
            return redirect(url_for("register"))
        # Add user to the Mongo DB
        else:
            register = {
                "username": request.form.get("username").lower(),
                "password": generate_password_hash(
                    request.form.get("password"))
            }
            mongo.db.users.insert_one(register)
            flash(f'Welcome, {request.form.get("username").capitalize()}')
            flash("Registration successfuly")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    """
    Registered user login
    Chsck if user is stored in the DB
    Verifies that a password matches a hash
    If user war verified The user is
    redirected to a profile page
    """

    if request.method == "POST":
        # check username exists in db
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})
        if existing_user:
            # Check password hash for match
            if check_password_hash(
                    existing_user["password"], request.form.get("password")):
                # Add user to session cookie
                session["user"] = request.form.get("username").lower()
                flash("Welcome, {}".format(
                    request.form.get("username").capitalize()), 'success')
                return redirect(url_for(
                    "profile", username=session["user"]))
        else:
            # If username doesn't exist
            flash("Incorrect Username and/or Password", 'error')
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):

    """
    Find user's username from db
    Check if user match session cookie
    Render Profile page if verified
    """
    if "user" in session:
        username = mongo.db.users.find_one(
            {"username": session["user"]})["username"]
        # Get categories from DB
        categories = mongo.db.categories.find()
        # IsButton=True show account button for profile page
        if session["user"]:
            posts = mongo.db.posts.find().sort('_id', -1)
            return render_template(
                "profile.html", username=username,
                isButton=True, categories=categories, posts=posts,  profile=True)
    # Rediret unauthorized users page access
    else:
        flash("Please log in or register", 'error')
        return redirect(url_for("login"))
    

@app.route("/delete_profile", methods=["GET", "POST"])
def delete_profile():

    """ 
    Delete user rofile Get input
    from form and find username
    and password in the DB For deletion
    """
    if "user" in session:
        if request.method == "POST":
            # check if username exists in db
            existing_user = mongo.db.users.find_one(
                {"username": request.form.get("username").lower()})
            if existing_user:
                # ensure hashed password matches user input
                if check_password_hash(
                        existing_user["password"], request.form.get("password")):
                    mongo.db.users.remove(existing_user)
                    flash("Good Buy", 'success')
                    return redirect(url_for("logout"))
                else:
                    # invalid password match
                    flash("Incorrect Username and/or Password", 'error')
                    return redirect(url_for("delete_profile", account=True))
            else:
                # username doesn't exist
                flash("Incorrect Username and/or Password", 'error')
                return redirect(url_for("delete_profile", account=True))

        return render_template("edit_profile.html", account=True)
        # Rediret unauthorized users page access
    else:
        flash("Please log in or register", 'error')
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    """
    remove the username from the session if it's there
    """
    # Remove session cookie
    if "user" in session:
        session.pop('user')
        return redirect(url_for('index'))
    # Rediret unauthorized users page access
    else:
        flash("Please log in or register", 'error')
        return redirect(url_for("login"))


@app.route("/add_post", methods=("POST", "GET"))
def add_post():
    """
    Add new posts to the Mongo DB
    Upload image to the Cloudinary API
    """
    if "user" in session:
        # Return all the categories form DB
        categories = mongo.db.categories.find()
        if request.method == "POST":
            upload_result = None
            image = None
            image_small = None
            if request.files:
                # File upoad to cloudinary
                folder = request.form.get("category").lower()
                file_to_upload = request.files['file']
                upload_result = upload(file_to_upload, folder=folder)
                # Get 1920p size image URL
                image, options = cloudinary_url(
                    upload_result['public_id'],
                    format="jpg", crop="fill", width=1920)
                # Get image thumblail URL
                image_small, options = cloudinary_url(
                    upload_result['public_id'],
                    format="jpg", crop="fill", width=300)
                # Get image public id
                img_id = upload_result.get('public_id')
                # requers url status
                URL_status = requests.get(image)
                # Submit post to Mongo DB if file upload was success
                if URL_status.status_code == 200:
                    submit = {
                        "category_name": request.form.get("category").lower(),
                        "title": request.form.get("title").lower(),
                        "description": request.form.get("description"),
                        "image": image,
                        "image_sm": image_small,
                        "img_id": img_id,
                        "created_by": session["user"],
                        "time_created": now
                        }
                    mongo.db.posts.insert_one(submit)
                    flash("Post was successfully added", 'success')
                    return redirect(url_for("add_post", categories=categories, post=True))
                else:
                    # failed cloudinary API
                    if URL_status.status_code != 200:
                        flash(f"Status code: {URL_status.status_code}")
                        flash("Post did not upload Try again", 'error')
                        return redirect(url_for("add_post", categories=categories, post=True))
                        # Failed to uplload to the mongo DB
                    else:
                        flash("Post failed upload", 'error')
                        flash("Please try again later", 'error')
                        return redirect(url_for("add_post", categories=categories, post=True))

        else:
            return render_template("add_post.html", categories=categories, post=True)
    # Rediret unauthorized users page access
    else:
        flash("Please log in or register", 'error')
        return redirect(url_for("login"))


@app.route("/edit_post/<post_id>", methods=["GET", "POST"])
def edit_post(post_id):

    """
    Update mongo DB "post" collection
    Update existing post Title and
    description only
    """
    if "user" in session:
        # Find existing post by id and get category
        post = mongo.db.posts.find_one({"_id": ObjectId(post_id)})
        categories = mongo.db.categories.find().sort("category_name", 1)

        # Get image id and url out of mongo DB
        for k, v in post.items():
            if k == "image":
                image = v
            elif k == "img_id":
                image_id = v
            elif k == "image_sm":
                image_sm = v
            elif k == "time_created":
                time_stamp = v

        # Update Object to be submitet for update
        if request.method == "POST":
            submit = {
                "category_name": request.form.get("category").lower(),
                "title": request.form.get("title").lower(),
                "description": request.form.get("description"),
                "image": image,
                "image_sm": image_sm,
                "img_id": image_id,
                "created_by": session["user"],
                "time_created": time_stamp
            }
            mongo.db.posts.update({"_id": ObjectId(post_id)}, submit)
            flash("post Successfully Updated", 'success')
            return redirect(url_for("profile", username=session["user"]))

        return render_template("edit_post.html", categories=categories, post=post)
    # Rediret unauthorized users page access
    else:
        flash("Please log in or register", 'error')
        return redirect(url_for("login"))
   

@app.route("/delete_post/<post_id>")
def delete_post(post_id):
    """
    DElete post from mongo DB
    Get image url trom DB and
    delete from cloudinary storage
    """
    if "user" in session:
        # Find post by id and iterate
        # over to extract image id and URL
        posts = mongo.db.posts.find_one(
            {"_id": ObjectId(post_id)}, {"img_id": 1, "_id": 0})
        for x, y in posts.items():
            if x == "img_id":
                image_id = y

        try:
            # Destroy permanently delete a single asset
            # Invalidates CDN cached copies of the asset
            cloudinary.uploader.destroy(image_id, invalidate='true')
            status = True
        # Catch error If try delete same asset again
        except AttributeError:
            flash("file already was deleted", 'error')
            return redirect(url_for("profile", username=session["user"]))

        if status:
            mongo.db.posts.remove({"_id": ObjectId(post_id)})
            flash("Post was successluly deleted", 'success')
        else:
            # Failed to destroy image from cloudinary
            flash("Failed to delete Image file", 'error')
            flash("Please try again later", 'error')
            return redirect(url_for("profile", username=session["user"]))

        return redirect(url_for("profile", username=session["user"]))
    # Rediret unauthorized users page access
    else:
        flash("Please log in or register", 'error')
        return redirect(url_for("login"))


@app.route('/gallery', methods=["GET", "POST"])
def gallery():
    """
    Gallery page
    Get all posts form DB
    """
    # mongo.db.posts.drop_indexes()
    # mongo.db.posts.create_index([
    #   ("title", "text"), ("description", "text"), ("created_by", "text")])
    categories = mongo.db.categories.find()
    posts = list(mongo.db.posts.find().sort('_id', -1))
    if request.method == "POST":
        search = request.form.get("search").lower()
        category_name = request.form.get("category").lower()
        categories = mongo.db.categories.find()
        # Search by keyword, username
        # Or Query posts by category
        test = "select category"
        # Search by keyword and category
        if search != "" and category_name != test:
            posts = list(mongo.db.posts.find({ "$and" : [ {
                "category_name": category_name }, {"$text": {"$search": search}}] }))
            if len(posts) == 0:     
                flash(f"No results for {search} in {category_name}", 'error')
                return render_template("gallery.html", posts=posts, 
                    categories=categories, title="gallery")
            else:
                flash(f"Results for {search} in {category_name}", 'success')
                return render_template("gallery.html", posts=posts,
                categories=categories, title="gallery")
        # Search by Keyword only
        elif search != "":
            posts = list(mongo.db.posts.find({"$text": {"$search": search}}))
            if len(posts) == 0:     
                flash(f"No results for {search}", 'error')
                return render_template("gallery.html", posts=posts, 
                    categories=categories, title="gallery")
            else:
                flash(f"Results for {search}", 'success')
                return render_template("gallery.html", posts=posts,
                categories=categories, title="gallery")
        # Search by category only
        elif category_name != test and search == "":
            posts = list(mongo.db.posts.find({"category_name": category_name }))
            if len(posts) == 0:     
                flash(f"No results for {category_name}", 'error')
                return render_template("gallery.html", posts=posts, 
                    categories=categories, title="gallery")
            else:
                flash(f"Results for category {category_name}", 'success')
                return render_template("gallery.html", posts=posts,
                categories=categories, title="gallery")
        else:
            return render_template("gallery.html", posts=posts,
                categories=categories, title="gallery")

    else:
        return render_template('gallery.html', posts=posts,
            categories=categories, title="gallery")

