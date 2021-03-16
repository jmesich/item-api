import asyncio
import sqlite3
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict

import aiohttp_jinja2
import jinja2
import aiosqlite
from aiohttp import web

async def fetch_item(db: aiosqlite.Connection, item_id:int) -> Dict[str,Any]:
    async with db.execute(
        "SELECT owner, editor, title, description , price, quantity FROM items where id =?",[item_id]
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Item {item_id} doesn't exist.")
        return {
            "id": item_id,
            "owner": row["owner"],
            "editor": row["editor"],
            "title": row["title"],
            "description": row["description"],
            "price": row["price"],
            "quantity": row["quantity"],
        }

router = web.RouteTableDef()

#this is applied to all aiohttp application routers
#gathers all our routes
@web.middleware
def handle_json_error(func: Callable[[web.Request], Awaitable[web.Response]]) -> Callable[[web.Request], Awaitable[web.Response]]:
    async def handler(request: web.Request) -> web.Response:
        #tries to get it to work
        try:
            return await func(request)
        except Exception as ex:
            return web.json_response({"status":"failed", "reason": str(ex)}, status =400)

    return handler

@router.get("/")
async def index(request: web.Request) -> web.Response:
    return web.Response(text=f"Placeholder Text")

#lists all the items
@router.get("/api")
async def api_list_items(request: web.Request) -> web.Response:
    ret =[]
    db = request.config_dict["DB"]
    async with db.execute("SELECT id, owner, editor, title,description,price,quantity FROM items") as cursor:
        async for row in cursor:
            ret.append(
                {
                    "id": row["id"],
                    "owner": row["owner"],
                    "editor": row["editor"],
                    "title": row["title"],
                    "description": row["description"],
                    "price": row["price"],
                    "quantity": row["quantity"],

                }
            )
    return web.json_response({"status":"ok","data":ret})


#adds new item
@router.post("/api")
async def api_new_item(request: web.Request)-> web.Response:
    #get the information from the post request
    post = await request.json()
    title = post["title"]
    owner = post["owner"]
    description = post["description"]
    price = post["price"]
    quantity = post["quantity"]
    db = request.config_dict["DB"]

    async with db.execute(
        "INSERT INTO items (owner,editor,title,description,price,quantity) VALUES(?,?,?,?,?,?)",
        [owner,owner,title,description,price,quantity],
    ) as cursor:
        item_id = cursor.lastrowid

    await db.commit()

    return web.json_response(
        {
            "status": "ok",
            "data": {
                "id":item_id,
                "owner":owner,
                "editor": owner,
                "title":title,
                "description": description,
                "price": price,
                "quantity": quantity,
            },
        })

#gets the requested item
@router.get("/api/{item}")
async def api_get_item(request: web.Request) -> web.Response:
    item_id = request.match_info["item"]
    db = request.config_dict["DB"]
    item = await fetch_item(db,item_id)
    return web.json_response(
        {
            "status": "ok",
            "data": {
                "id": item_id,
                "owner": item["owner"],
                "editor": item["editor"],
                "title": item["title"],
                "description": item["description"],
                "price": item["price"],
                "quantity": item["quantity"],
            }
        }
    )
#deletes an item
@router.delete("/api/{item}")
async def api_del_item(request: web.Request) -> web.Response:
    item_id = request.match_info["item"]
    db = request.config_dict["DB"]
    async with db.execute("DELETE FROM items WHERE id = ?",item_id) as cursor:
        if cursor.rowcount == 0:
            return web.json_response(
                {"status": "fail", "reason":f"item {item_id} doesn't exist."},status=404,
            )
    await db.commit()
    return web.json_response({"status":"ok","id":item_id})

@router.patch("/api/{item}")
async def api_update_post(request: web.Request) -> web.Response:
    item_id = request.match_info["item"]
    item = await request.json()
    db = request.config_dict["DB"]
    fields = {}

    if "title" in item:
        fields["title"]= item["title"]
    if "description" in item:
        fields["description"] = item["description"]
    if "editor" in item:
        fields["editor"] = item["editor"]
    #if it is not empty the
    if fields:
        fields_names = ", ".join(f"{name} = ?" for name in fields)
        field_values = list(fields.values())
        await db.execute(
            f"UPDATE items SET {fields_names} WHERE id = ?", field_values + [item_id]
        )
        await db.commit()
    new_item = await fetch_item(db,item_id)
    return web.json_response(
        {"status": "ok",
        "data" : {
            "id":  new_item["id"],
            "owner": new_item["owner"],
            "editor": new_item["editor"],
            "title": new_item["title"],
            "description": new_item["description"],
            "price": new_item["price"],
            "quantity": new_item["quantity"],
            },
        }
    )

def get_db_path() -> Path:
    here = Path.cwd()
    while not (here/".git").exists():
        if here == here.parent:
            raise RuntimeError("Cannot find root github dir")
        here = here.parent
    return here / "db.sqlite3"

async def init_db(app: web.Application) -> AsyncIterator[None]:
    sqlite_db = get_db_path()
    db = await aiosqlite.connect(sqlite_db)
    db.row_factory = aiosqlite.Row
    app["DB"] = db
    yield
    await db.close()

async def init_app() -> web.Application:
    app = web.Application(middlewares=[handle_json_error])
    app.add_routes(router)
    app.cleanup_ctx(init_db)
    return app

def try_make_db():
    sqlite_db = get_db_path()
    if sqlite_db.exists():
        return

    with sqlite3.connect(sqlite_db) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE items (
        id INTEGER PRIMARY KEY,
        title TEXT,
        description TEXT,
        owner TEXT,
        editor TEXT,
        price INTEGER,
        quantity INTEGER)
        """)
        conn.commit()

try_make_db()
web.run_app(init_app())


