"""Agenda builder (Phase 3) — CRUD over session agenda items.

Facilitators create ordered agenda items with time budgets, map types, and
reorder via drag-and-drop. All operations are scoped to session ownership.
"""
import json
from datetime import datetime, timedelta

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, jsonify)
from flask_login import login_required, current_user

from models import (db, AgendaItem, Session, owned, MAP_TYPES, AGENDA_TYPES,
                    CATEGORIES, DEFAULT_SECTIONS)

agenda_bp = Blueprint("agenda", __name__)


def _get_session_or_404(session_id):
    s = owned(Session, current_user).filter(Session.id == session_id).first()
    if s is None:
        abort(404)
    return s


def _get_agenda_item_or_404(item_id):
    item = AgendaItem.query.filter(AgendaItem.id == item_id).first()
    if item is None:
        abort(404)
    # Check ownership via session
    s = owned(Session, current_user).filter(
        Session.id == item.session_id).first()
    if s is None:
        abort(404)
    return item


def _validate_agenda_item(data):
    errors = []
    if not data.get("name", "").strip():
        errors.append("Name is required.")
    if not data.get("category", "").strip():
        errors.append("Category is required.")
    if data.get("category") not in CATEGORIES:
        errors.append("Invalid category.")
    if not data.get("type"):
        errors.append("Type is required.")
    if data.get("type") not in AGENDA_TYPES:
        errors.append("Invalid type.")
    duration = data.get("duration_min")
    if not duration:
        errors.append("Duration is required.")
    else:
        try:
            if int(duration) <= 0:
                errors.append("Duration must be > 0.")
        except (ValueError, TypeError):
            errors.append("Duration must be a number.")
    if data.get("map_type") and data.get("map_type") not in MAP_TYPES:
        errors.append("Invalid map type.")
    return errors


def _calculate_timeline(agenda_items, session_start_hour=9):
    """Calculate start/end times for each agenda item.

    Args:
        agenda_items: list of AgendaItem objects, ordered by position
        session_start_hour: default 9 (09:00 AM)

    Returns:
        list of dicts with {item_id, start_time, end_time, total_minutes}
    """
    timeline = []
    current_minutes = session_start_hour * 60  # Convert hours to minutes

    for item in agenda_items:
        if not item.enabled:
            continue
        start_h = current_minutes // 60
        start_m = current_minutes % 60
        end_minutes = current_minutes + item.duration_min
        end_h = end_minutes // 60
        end_m = end_minutes % 60

        timeline.append({
            "item_id": item.id,
            "start_time": f"{start_h:02d}:{start_m:02d}",
            "end_time": f"{end_h:02d}:{end_m:02d}",
            "duration_min": item.duration_min
        })
        current_minutes = end_minutes

    return timeline


def _serialize_agenda_item(item):
    """Convert AgendaItem to dict for JSON responses."""
    return {
        "id": item.id,
        "position": item.position,
        "type": item.type,
        "name": item.name,
        "category": item.category,
        "duration_min": item.duration_min,
        "description": item.description,
        "activities": item.get_activities(),
        "tips": item.get_tips(),
        "roles": item.roles,
        "materials": item.materials,
        "output": item.output,
        "map_type": item.map_type,
        "enabled": item.enabled,
        "created_at": item.created_at.isoformat()
    }


# ---------------------------------------------------------------- list + create agenda
@agenda_bp.route("/sessions/<int:session_id>/agenda", methods=["GET", "POST"])
@login_required
def agenda_list(session_id):
    s = _get_session_or_404(session_id)

    if request.method == "POST":
        data = request.form
        errors = _validate_agenda_item(data)
        if errors:
            flash("\n".join(errors), "error")
            items = AgendaItem.query.filter(
                AgendaItem.session_id == s.id).order_by(AgendaItem.position).all()
            timeline = _calculate_timeline(items)
            timeline_dict = {t["item_id"]: t for t in timeline}
            total_minutes = sum(i.duration_min for i in items if i.enabled)
            return render_template(
                "agenda_list.html",
                session=s,
                agenda_items=items,
                timeline=timeline_dict,
                total_minutes=total_minutes,
                categories=CATEGORIES,
                map_types=MAP_TYPES,
                default_sections=DEFAULT_SECTIONS
            ), 400

        # Get next position
        max_pos = db.session.query(
            db.func.max(AgendaItem.position)).filter(
            AgendaItem.session_id == s.id).scalar() or -1
        next_position = max_pos + 1

        # Parse activities and tips as JSON
        activities = data.get("activities", "").strip().split("\n")
        activities = [a.strip() for a in activities if a.strip()]
        tips = data.get("tips", "").strip().split("\n")
        tips = [t.strip() for t in tips if t.strip()]

        item = AgendaItem(
            session_id=s.id,
            position=next_position,
            type=data.get("type", "section"),
            name=data.get("name", "").strip(),
            category=data.get("category", "").strip(),
            duration_min=int(data.get("duration_min", 0)),
            description=data.get("description", "").strip(),
            roles=data.get("roles", "").strip(),
            materials=data.get("materials", "").strip(),
            output=data.get("output", "").strip(),
            map_type=data.get("map_type") or None,
            enabled=request.form.get("enabled") == "on"
        )
        item.set_activities(activities)
        item.set_tips(tips)

        db.session.add(item)
        db.session.commit()
        flash("Agenda item added.", "ok")
        return redirect(url_for("agenda.agenda_list", session_id=s.id))

    # GET: render agenda list
    items = AgendaItem.query.filter(
        AgendaItem.session_id == s.id).order_by(AgendaItem.position).all()

    # Calculate timeline
    timeline = _calculate_timeline(items)
    timeline_dict = {t["item_id"]: t for t in timeline}

    # Calculate total minutes (enabled items only)
    total_minutes = sum(i.duration_min for i in items if i.enabled)

    return render_template(
        "agenda_list.html",
        session=s,
        agenda_items=items,
        timeline=timeline_dict,
        total_minutes=total_minutes,
        categories=CATEGORIES,
        map_types=MAP_TYPES,
        default_sections=DEFAULT_SECTIONS
    )


# ---------------------------------------------------------------- edit agenda item
@agenda_bp.route("/sessions/<int:session_id>/agenda/<int:item_id>/edit",
                  methods=["GET", "POST"])
@login_required
def edit_agenda_item(session_id, item_id):
    s = _get_session_or_404(session_id)
    item = _get_agenda_item_or_404(item_id)

    if item.session_id != s.id:
        abort(404)

    if request.method == "POST":
        data = request.form
        errors = _validate_agenda_item(data)
        if errors:
            flash("\n".join(errors), "error")
            return render_template(
                "agenda_form.html",
                session=s,
                item=item,
                categories=CATEGORIES,
                map_types=MAP_TYPES,
                default_sections=DEFAULT_SECTIONS,
                action="edit"
            ), 400

        item.type = data.get("type", "section")
        item.name = data.get("name", "").strip()
        item.category = data.get("category", "").strip()
        item.duration_min = int(data.get("duration_min", 0))
        item.description = data.get("description", "").strip()
        item.roles = data.get("roles", "").strip()
        item.materials = data.get("materials", "").strip()
        item.output = data.get("output", "").strip()
        item.map_type = data.get("map_type") or None
        item.enabled = request.form.get("enabled") == "on"

        # Parse activities and tips
        activities = data.get("activities", "").strip().split("\n")
        activities = [a.strip() for a in activities if a.strip()]
        tips = data.get("tips", "").strip().split("\n")
        tips = [t.strip() for t in tips if t.strip()]
        item.set_activities(activities)
        item.set_tips(tips)

        db.session.commit()
        flash("Agenda item updated.", "ok")
        return redirect(url_for("agenda.agenda_list", session_id=s.id))

    # GET: render edit form
    return render_template(
        "agenda_form.html",
        session=s,
        item=item,
        categories=CATEGORIES,
        map_types=MAP_TYPES,
        default_sections=DEFAULT_SECTIONS,
        action="edit"
    )


# ---------------------------------------------------------------- delete agenda item
@agenda_bp.route("/sessions/<int:session_id>/agenda/<int:item_id>/delete",
                  methods=["POST"])
@login_required
def delete_agenda_item(session_id, item_id):
    s = _get_session_or_404(session_id)
    item = _get_agenda_item_or_404(item_id)

    if item.session_id != s.id:
        abort(404)

    deleted_position = item.position
    db.session.delete(item)
    db.session.commit()

    # Compact positions: items after deleted position shift down
    items_after = AgendaItem.query.filter(
        AgendaItem.session_id == s.id,
        AgendaItem.position > deleted_position
    ).order_by(AgendaItem.position).all()

    for i, shifted_item in enumerate(items_after):
        shifted_item.position = deleted_position + i
    db.session.commit()

    flash("Agenda item deleted.", "ok")
    return redirect(url_for("agenda.agenda_list", session_id=s.id))


# ---------------------------------------------------------------- reorder agenda items (drag-and-drop)
@agenda_bp.route("/sessions/<int:session_id>/agenda/reorder", methods=["POST"])
@login_required
def reorder_agenda_items(session_id):
    s = _get_session_or_404(session_id)

    data = request.get_json()
    if not data or "items" not in data:
        return jsonify(error="Invalid request"), 400

    try:
        items_order = data["items"]  # [{"id": 1, "position": 0}, ...]
        # Use negative placeholders to avoid unique constraint violations during reorder
        for idx, order in enumerate(items_order):
            item = AgendaItem.query.filter(
                AgendaItem.id == order["id"],
                AgendaItem.session_id == s.id
            ).first()
            if not item:
                return jsonify(error="Item not found"), 404
            item.position = -(idx + 1)  # Temporary negative positions
        db.session.commit()

        # Now set final positions
        for order in items_order:
            item = AgendaItem.query.filter(
                AgendaItem.id == order["id"],
                AgendaItem.session_id == s.id
            ).first()
            item.position = order["position"]
        db.session.commit()
        return jsonify(success=True), 200
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Invalid request format"), 400


# ---------------------------------------------------------------- get agenda + timeline (JSON API)
@agenda_bp.route("/api/sessions/<int:session_id>/agenda", methods=["GET"])
@login_required
def api_agenda(session_id):
    s = _get_session_or_404(session_id)

    items = AgendaItem.query.filter(
        AgendaItem.session_id == s.id).order_by(AgendaItem.position).all()

    timeline = _calculate_timeline(items)
    total_minutes = sum(i.duration_min for i in items if i.enabled)

    return jsonify({
        "session_id": s.id,
        "agenda_items": [_serialize_agenda_item(i) for i in items],
        "timeline": timeline,
        "total_minutes": total_minutes,
        "total_hours": total_minutes / 60
    }), 200


# ---------------------------------------------------------------- get section library (JSON API)
@agenda_bp.route("/api/sections", methods=["GET"])
@login_required
def api_sections():
    return jsonify({
        "sections": DEFAULT_SECTIONS,
        "categories": list(CATEGORIES)
    }), 200
