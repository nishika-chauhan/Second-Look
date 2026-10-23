"""Internal HTTP service for the Second Look gantry simulator."""

import asyncio
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from sim import gantry_demo as demo

app = FastAPI(title="Second Look Simulator Service")
simulation_lock = threading.Lock()


class PickPlaceCommand(BaseModel):
    target: str = "cup_red"
    x: float = Field(default=0.15, ge=-0.5, le=0.5)
    y: float = Field(default=-0.20, ge=-0.5, le=0.5)
    z_rest: float = Field(default=0.04, ge=0.0, le=0.3)


@app.get("/health")
async def health():
    return {"ok": True, "service": "simulator"}


def execute_pick_place(command: PickPlaceCommand):
    # The current gantry demo supports cup_red.
    if command.target != "cup_red":
        raise ValueError("The gantry demo currently supports only cup_red.")

    with simulation_lock:
        started = demo.pick(command.target)

        if not started:
            return {
                "ok": False,
                "stage": "pick",
                "message": "The gantry could not complete the pick.",
                "simulation_time": float(demo.data.time),
            }

        placed = demo.place(command.x, command.y, command.z_rest)

        return {
            "ok": bool(placed),
            "stage": "complete" if placed else "place",
            "target": command.target,
            "final_position": demo.obj_pos(command.target).round(4).tolist(),
            "simulation_time": round(float(demo.data.time), 3),
        }


@app.post("/command")
async def command(command: PickPlaceCommand):
    try:
        return await run_in_threadpool(execute_pick_place, command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Simulator command failed: {type(exc).__name__}",
        ) from exc
