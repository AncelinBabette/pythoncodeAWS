import os
import uuid
from flask import Flask, render_template, request
import boto3
import pymysql
from werkzeug.utils import secure_filename

app = Flask(__name__)
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "student-photos-ancelin-2026")
AWS_REGION = os.environ.get("AWS_REGION", "eu-north-1")

def get_db_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "studentdb"),
        port=3306,
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor
    )


s3 = boto3.client("s3", region_name=AWS_REGION)


@app.route("/", methods=["GET", "POST"])
def index():
    message = None
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        course = request.form.get("course", "").strip()
        photo = request.files.get("photo")

        if not name or not email:
            error = "Name and email are required."
        elif not photo or not photo.filename:
            error = "Please select a photo."
        else:
            connection = None
            photo_key = None

            try:
                filename = secure_filename(photo.filename)
                extension = os.path.splitext(filename)[1]
                photo_key = (
                    f"student-photos/{uuid.uuid4().hex}{extension}"
                )

                # Upload the photo to the private S3 bucket.
                s3.upload_fileobj(
                    photo,
                    S3_BUCKET_NAME,
                    photo_key,
                    ExtraArgs={
                        "ContentType": (
                            photo.mimetype or "application/octet-stream"
                        )
                    }
                )

                # Save the S3 object key in MySQL.
                # The bucket does not need public access.
                connection = get_db_connection()

                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO students
                            (name, email, course, photo_url)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (name, email, course, photo_key)
                    )

                connection.commit()
                message = "Student registered and photo uploaded successfully."

            except Exception:
                if connection:
                    connection.rollback()

                app.logger.exception("Student registration failed")
                error = (
                    "Registration failed. Check the application logs "
                    "and AWS configuration."
                )

            finally:
                if connection:
                    connection.close()

    return render_template(
        "index.html",
        message=message,
        error=error
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
