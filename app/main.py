from sqlite3 import IntegrityError
from authx import AuthX
import hashlib
import uvicorn

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from config import *

app = FastAPI()

jwt_authx = AuthX(config=config_jwt)
jwt_authx.handle_errors(app)

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # errors = [e["msg"] for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"detail": "Ошибка валидации имени или пароля"}
    )

@app.post("/api/v1/users/registration", summary="Регистрация", tags=["User"])
def registration(usershema: UsersShema):
    conn = sqlite3.connect("MyDB.db")
    cursor = conn.cursor()
    hash_password = hashlib.md5(usershema.password.encode()).hexdigest()
    try:
        cursor.execute(
                "INSERT INTO users (name, password) VALUES (?, ?)",
                (usershema.name , hash_password)
            )
        token = jwt_authx.create_access_token(uid=usershema.name)

        conn.commit()
        return {"detail": "Пользователь добавлен",
                "token": token
                }

    except IntegrityError:
        raise HTTPException(status_code=401, detail="Пользователь есть")
    finally:
        conn.close()


@app.post("/api/v1/users/authorization", summary="Вход", tags=["User"])
def authorization(usershema: UsersShema):
    with sqlite3.connect("MyDB.db") as conn:
        hash_password = hashlib.md5(usershema.password.encode()).hexdigest()

        user = conn.cursor().execute("select * from users where name = ? and password = ?",
                              (usershema.name, hash_password)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Не верный логин или пароль")
        return {"detail": "Вы вошли"}

@app.post("/api/v1/users/return_all_users", summary="Вывод всех пользователей", tags=["User"])
def return_all_users():
    with sqlite3.connect("MyDB.db") as conn:
        cursor = conn.cursor()
        users = cursor.execute("select * from users").fetchall()
        return users


@app.post("/api/v1/forms", summary="Создание формы", tags=["Forms"] )
def create_forms(form: FormCreateSchema):
    with sqlite3.connect("MyDB.db") as conn:
        cursor = conn.cursor()

        user = cursor.execute("select * from users where id = ?",
                              ( form.user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Не такого пользователя")

        cursor.execute("insert into forms (user_id, user_name, title, description) values(?, ?, ?, ?)",
                       (form.user_id, form.user_name, form.title, form.description))
        form_id = cursor.lastrowid

        for f in form.fields:
            option_str = ",".join(f.options) if f.options else None
            cursor.execute("insert into field (form_id, type, label, options) values (?, ?, ?, ?)",
                           (form_id, f.type, f.label, option_str))
        conn.commit()
        return {"detail": "Форма создана"}

@app.get("/api/v1/forms/{form_id}", summary="Вывод вормы по её id", tags=["Forms"])
def output_forms(form_id: int):
    with sqlite3.connect("MyDB.db") as conn:
        cursor = conn.cursor()
        form = cursor.execute("select * from forms where id = ?", (form_id, )).fetchone()

        if not form:
            raise HTTPException(status_code=404, detail="нет такой формы")

        fields = cursor.execute("select id, type, label, options from field where form_id = ?", (form_id, )).fetchall()
        fields_data = []
        for f in fields:
            fields_data.append({
                "id": f[0],
                "type": f[1],
                "label": f[2],
                "options": f[3].split(",") if f[3] else None
            })

        return {"detail":({
                "id": form[0],
                "user_id": form[1],
                "user_name": form[2],
                "title": form[3],
                "description": form[4],
                "fields": fields_data
                })
        }

@app.put("/api/v1/forms/{form_id}", summary="Обновление формы", tags=["Forms"])
def update_forms(form_id: int, form: FormCreateSchema):
    with sqlite3.connect("MyDB.db") as conn:
        cursor = conn.cursor()
        form_execute = cursor.execute("select * from forms where id = ?", (form_id, )).fetchone()

        if not form_execute:
            raise HTTPException(status_code=404, detail="нет такой формы")

        cursor.execute("update forms set title = ?, description = ? where id = ?", (form.title, form.description, form_id))
        cursor.execute("delete from field where form_id = ?", (form_id, ))


        for f in form.fields:
            option_str = ",".join(f.options) if f.options else None
            cursor.execute("insert into field (form_id, type, label, options) values (?, ?, ?, ?)",
                           (form_id, f.type, f.label, option_str))
        conn.commit()
        return {"detail": "Форма обновлена"}

@app.delete("/api/v1/forms/{form_id}", summary="Удаление формы", tags=["Forms"])
def delete_forms(form_id: int):
    with sqlite3.connect("MyDB.db") as conn:
        cursor = conn.cursor()

        if not cursor.execute("select * from forms where id = ?", (form_id, )).fetchone():
            raise HTTPException(status_code=404, detail="Формы нет")

        cursor.execute("delete from forms where id = ?", (form_id, ))
        cursor.execute("delete from field where form_id= ?", (form_id, ))
        return {"detail": "Форма удалена"}

@app.get("/api/v1/users/{user_id}/forms", summary="Получение все форм пользователя по id",  tags=["Forms"])
def get_form_by_user(user_id):
    with sqlite3.connect("MyDB.db") as conn:
        cursor = conn.cursor()

        forms = cursor.execute("SELECT id, title, description FROM forms WHERE user_id = ?", (user_id,)).fetchall()

        if not forms:
            raise HTTPException(status_code=404, detail="У пользователя нет форм")

        return {
            "detail": [
                {
                    "id": f[0],
                    "title": f[1],
                    "description": f[2]
                } for f in forms
            ]
        }

@app.post("/api/v1/forms/submit", summary="Ответ на форму", tags=["Forms"])
def submit_response(response: ResponseSchema):
    with sqlite3.connect("MyDB.db") as conn:
        cursor = conn.cursor()

        if not cursor.execute("select * from forms where id = ?", (response.form_id, )).fetchone():
            raise HTTPException(status_code=404, detail="Нет такой формы")

        cursor.execute("insert into responses (form_id) values(?)", (response.form_id, ))
        response_id = cursor.lastrowid

        for ans in response.answers:
            cursor.execute("insert into answers (responses_id, field_id, value) values (?, ?, ?)", (response_id, ans.field_id, ans.value))

        conn.commit()

    return {"detail": "Ответ отправлен"}

if __name__ == '__main__':
    uvicorn.run("main:app", reload=True)