"""
Groups and Students CRUD — teacher-owned class lists.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import any_authenticated
from app.database import get_db
from app.models.check import Check
from app.models.group import Group, Student
from app.models.user import User

router = APIRouter(prefix="/groups", tags=["groups"])


class StudentOut(BaseModel):
    id: uuid.UUID
    name: str
    checks_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupOut(BaseModel):
    id: uuid.UUID
    name: str
    students: list[StudentOut]
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    name: str


class StudentCreate(BaseModel):
    name: str


@router.get("", response_model=list[GroupOut])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    """List current user's groups with embedded students and check counts."""
    groups_q = await db.execute(
        select(Group)
        .where(Group.teacher_id == current_user.id)
        .order_by(Group.created_at.asc())
    )
    groups = groups_q.scalars().all()

    if not groups:
        return []

    group_ids = [g.id for g in groups]

    students_q = await db.execute(
        select(Student)
        .where(Student.group_id.in_(group_ids))
        .order_by(Student.created_at.asc())
    )
    all_students = students_q.scalars().all()

    # Check counts per student name for this teacher
    student_names = list({s.name for s in all_students})
    if student_names:
        counts_q = await db.execute(
            select(Check.student_name, func.count().label("cnt"))
            .where(
                Check.submitted_by == current_user.id,
                Check.student_name.in_(student_names),
            )
            .group_by(Check.student_name)
        )
        counts_map: dict[str, int] = {row.student_name: row.cnt for row in counts_q.all()}
    else:
        counts_map = {}

    students_by_group: dict[uuid.UUID, list[StudentOut]] = {}
    for s in all_students:
        gid = s.group_id
        if gid not in students_by_group:
            students_by_group[gid] = []
        students_by_group[gid].append(StudentOut(
            id=s.id,
            name=s.name,
            checks_count=counts_map.get(s.name, 0),
            created_at=s.created_at,
        ))

    return [
        GroupOut(
            id=g.id,
            name=g.name,
            students=students_by_group.get(g.id, []),
            created_at=g.created_at,
        )
        for g in groups
    ]


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    group = Group(
        name=data.name.strip(),
        org_id=current_user.org_id,
        teacher_id=current_user.id,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return GroupOut(id=group.id, name=group.name, students=[], created_at=group.created_at)


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.teacher_id == current_user.id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.delete(group)
    await db.commit()
    return Response(status_code=204)


@router.post("/{group_id}/students", response_model=StudentOut, status_code=201)
async def add_student(
    group_id: uuid.UUID,
    data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.teacher_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Group not found")
    student = Student(group_id=group_id, name=data.name.strip())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return StudentOut(id=student.id, name=student.name, checks_count=0, created_at=student.created_at)


@router.delete("/{group_id}/students/{student_id}", status_code=204)
async def remove_student(
    group_id: uuid.UUID,
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(any_authenticated),
):
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.teacher_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Group not found")
    s_result = await db.execute(
        select(Student).where(Student.id == student_id, Student.group_id == group_id)
    )
    student = s_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    await db.delete(student)
    await db.commit()
    return Response(status_code=204)
