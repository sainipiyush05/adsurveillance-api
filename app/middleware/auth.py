"""
Authentication middleware for AdSurveillance
"""
import os
import jwt
from functools import wraps
from flask import request, jsonify
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY")

def token_required(f):
    """
    Decorator to require JWT token authentication
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Also check in request body for backward compatibility
        if not token and request.is_json:
            data = request.get_json()
            token = data.get('token') or data.get('user_id')
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication token is required'
            }), 401
        
        try:
            # Decode token
            secret_to_use = str(SECRET_KEY) if SECRET_KEY else None
            if not secret_to_use:
                return jsonify({
                    'success': False,
                    'error': 'Server configuration error'
                }), 500
            
            payload = jwt.decode(token, secret_to_use, algorithms=["HS256"])
            user_id = payload.get('user_id')
            
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': 'Invalid token payload'
                }), 401
            
            # Add user_id to request context
            request.user_id = str(user_id)
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': 'Token has expired. Please login again.'
            }), 401
        except jwt.InvalidTokenError as e:
            print(f"JWT decode error: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Invalid token: {str(e)}'
            }), 401
        except Exception as e:
            print(f"Token processing error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Failed to process token'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated