#!/usr/bin/env python3
"""Test script to verify worker is processing research tasks."""

import asyncio
import uuid

from app.db.base import get_db
from app.services.storage import storage_service
from app.services.task_queue import task_queue


async def test_worker():
    """Submit a test research task and monitor its status."""
    # Create a test task
    task_id = str(uuid.uuid4())
    query = "What is machine learning?"

    print(f"Creating test task: {task_id}")
    print(f"Query: {query}")

    async for db in get_db():
        # Create task in database
        await storage_service.create_task(
            db=db,
            task_id=task_id,
            query=query,
            depth="quick",
            scenario="academic",
            user_id="test-user-123",  # Test user ID
        )

        # Update to queued
        await storage_service.update_task_status(db, task_id, "queued")
        await db.commit()
        print("✓ Task created in database")

        # Enqueue for processing
        job_id = await task_queue.enqueue_research_task(
            task_id=task_id,
            query=query,
            depth="quick",
            scenario="academic",
            user_id="test-user-123",
        )
        print(f"✓ Task enqueued with job_id: {job_id}")

        # Wait and check status
        print("\nMonitoring task status (will check every 2 seconds for 30 seconds):")
        for i in range(15):
            await asyncio.sleep(2)
            task = await storage_service.get_task(db, task_id)
            status = task.status if task else "not found"
            progress = task.progress if task else 0
            print(f"  [{i*2}s] Status: {status}, Progress: {progress}%")

            if status in ["completed", "failed", "cancelled"]:
                print(f"\n✓ Task finished with status: {status}")
                if status == "completed" and task.report:
                    print(f"\nReport preview (first 200 chars):")
                    print(task.report[:200] + "...")
                elif status == "failed" and task.error:
                    print(f"\n✗ Error: {task.error}")
                break
        else:
            print("\n⚠ Task still processing after 30 seconds")

        # Cleanup
        await task_queue.close()
        break


if __name__ == "__main__":
    print("=" * 60)
    print("Worker Test Script")
    print("=" * 60)
    print()

    asyncio.run(test_worker())

    print()
    print("=" * 60)
    print("Test complete!")
    print("=" * 60)
