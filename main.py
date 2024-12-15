from fastapi import FastAPI

from api.v1.api import api_router


app = FastAPI(debug=True, title="OutOfSight")
app.include_router(router=api_router)

if __name__ == '__main__':
    import unicorn
    unicorn.run('main.app', reload=True, log_level="debug")
