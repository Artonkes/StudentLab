import sqlite3
from pydantic import BaseModel, Field
from typing import Optional, List
from authx import AuthXConfig

config_jwt = AuthXConfig(
    JWT_ALGORITHM = "HS256",
    JWT_SECRET_KEY = "SECRET_KEY",
    JWT_TOKEN_LOCATION = ['headers']
)

class UsersShema(BaseModel):
    name: str = Field(min_length=4, max_length=10)
    password: str = Field(min_length=6, max_length=16)

class FieldSchema(BaseModel):
    type: str  # 'text', 'radio', 'checkbox'
    label: str
    options: Optional[List[str]] = None

class FormCreateSchema(BaseModel):
    user_name: str
    user_id: int
    title: str
    description: Optional[str]
    fields: List[FieldSchema]

class AnswerSchema(BaseModel):
    field_id: int
    value: str

class ResponseSchema(BaseModel):
    form_id: int
    answers: List[AnswerSchema]

with sqlite3.connect("MyDB.db") as conn:
    cursor = conn.cursor()
    cursor.execute("""
        create table if not exists users (
            id integer primary key autoincrement, 
            name text unique, 
            password text, 
            jwt text
        );""")

    cursor.execute("""
        create table if not exists forms(
            id integer primary key,
            user_id integer,
            user_name text,
            title text,
            description text,
            foreign key (user_id) references users(id) 
            foreign key (user_name) references users(name) 
        );""")

    cursor.execute("""
        create table if not exists field(
            id integer primary key autoincrement,
            form_id integer,
            type text,
            label text,
            options text,
            foreign key (form_id) references forms(id) 
        );""")

    cursor.execute("""
        create table if not exists responses(
            id integer primary key autoincrement,
            form_id integer,
            foreign key(form_id) references form(id)
        );""")

    cursor.execute("""
        create table if not exists answers(
            id integer primary key autoincrement,
            responses_id integer,
            field_id integer,
            value text,
            foreign key(responses_id) references responses(id),
            foreign key(field_id) references field(id)
        );""")


    conn.commit()
