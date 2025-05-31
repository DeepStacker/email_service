import random
import time

otp_store = {}

def generate_otp(length=6):
    return ''.join(random.choices('0123456789', k=length))

pass

import threading

otp_store_lock = threading.Lock()

def store_otp(email, otp):
    with otp_store_lock:
        otp_store[email] = {"otp": otp, "timestamp": time.time()}

def verify_otp(email, otp):
    with otp_store_lock:
        record = otp_store.get(email)
        if not record:
            return False
        # OTP expires in 5 minutes
        if time.time() - record["timestamp"] > 300:
            otp_store.pop(email, None)
            return False
        if record["otp"] == otp:
            return True
        return False
