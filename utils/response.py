def success(data=None, message="OK"):
    return {
        "success": True,
        "message": message,
        "data": data
    }

def fail(message="Error"):
    return {
        "success": False,
        "message": message
    }