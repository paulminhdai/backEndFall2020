from datetime import datetime, timedelta
from email_validator import validate_email, EmailNotValidError
from flask import jsonify, request
from sqlalchemy.exc import IntegrityError
from zxcvbn import zxcvbn
from api.helpers import GENERIC_ERROR, requires_json, validate_types
from config import app, db, DEBUG
from database.user import User
from database.session import Session


@app.route('/login', methods=['POST'])
@requires_json
@validate_types({'email': str, 'password': str})
def login(email, password, **kwargs):
    try:
        email_results = validate_email(email)
        email = email_results.email  # normalizes our email
    except EmailNotValidError as ex:
        # Treat verification failure as normal login failure
        return jsonify({'success': False, 'message': 'Invalid login details'})

    user = db.session.query(User).filter(User.email == email).limit(1).first()
    if user == None or not user.verify_password(password):
        return jsonify({'success': False, 'message': 'Invalid login details'})

    session = Session(user_id=user.user_id, expires=datetime.now() + timedelta(days=1))
    db.session.add(session)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '',
        'session': session.session_id,
        'expires': session.expires
    })


@app.route('/signup', methods=['POST'])
@requires_json
@validate_types({'name': str, 'email': str, 'password': str})
def signup(name, email, password, **kwargs):
    # Validate name
    min_length = 2
    max_length = User.__table__.c['name'].type.length
    if len(name) < min_length:
        return jsonify({'success': False, 'message': 'Name should be at least {0} characters long'.format(min_length)})
    if len(name) > max_length:
        return jsonify({'success': False, 'message': 'Name should be at most {0} characters long'.format(max_length)})

    # Validate email
    try:
        email_results = validate_email(email)
        email = email_results.email  # normalizes our email
    except EmailNotValidError as ex:
        return jsonify({'success': False, 'message': str(ex)})

    # Ensure strong password
    password_results = zxcvbn(password, user_inputs=[name, email])
    if password_results['score'] < 2:
        suggestions = password_results['feedback']['suggestions']
        response = {'success': False, 'message': 'Your password is too weak'}
        if len(suggestions) > 0:
            response['message'] += ' - {0}'.format(suggestions[0])
        return jsonify(response)

    # Finally create user and session
    try:
        user = User(email=email, name=name, password=password)
        db.session.add(user)
        db.session.commit()
    except IntegrityError as ex:
        return jsonify({'success': False, 'message': 'Email already registered'})

    session = Session(user_id=user.user_id, expires=datetime.now() + timedelta(days=1))
    db.session.add(session)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '',
        'session': session.session_id,
        'expires': session.expires
    })
