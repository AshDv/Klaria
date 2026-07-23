"""Information, accords et droits RGPD des utilisateurs."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import current_user
from app.config import settings
from app.db import get_session
from app.models import (
    ConsentSession,
    ExternalIdentity,
    ParticipantConsent,
    Recording,
    SessionRecording,
    StructuredReport,
    User,
    UserAgreement,
)

router = APIRouter(prefix="/api")


class AgreementInput(BaseModel):
    terms_accepted: bool
    privacy_accepted: bool


class DeleteAccountInput(BaseModel):
    confirmation: str


def has_current_agreements(user_id: str, db: Session) -> bool:
    agreement = db.exec(
        select(UserAgreement)
        .where(
            UserAgreement.user_id == user_id,
            UserAgreement.terms_version == settings.terms_version,
            UserAgreement.privacy_version == settings.privacy_version,
        )
        .order_by(UserAgreement.accepted_at.desc())
    ).first()
    return bool(agreement)


def save_agreements(user_id: str, payload: AgreementInput, db: Session) -> None:
    if not payload.terms_accepted or not payload.privacy_accepted:
        raise HTTPException(400, "Les CGU et l’information RGPD doivent être acceptées")
    if not has_current_agreements(user_id, db):
        db.add(
            UserAgreement(
                user_id=user_id,
                terms_version=settings.terms_version,
                privacy_version=settings.privacy_version,
            )
        )
        db.commit()


@router.get("/legal/notices")
def legal_notices():
    return {
        "terms_version": settings.terms_version,
        "privacy_version": settings.privacy_version,
        "controller": settings.data_controller_name or "À renseigner avant production",
        "controller_address": settings.data_controller_address or "À renseigner avant production",
        "privacy_contact": settings.privacy_contact_email,
        "processing": [
            "Compte : e-mail, nom, mot de passe hashé et accords.",
            "Réunion : noms et e-mails des invités jusqu’à suppression.",
            "Audio : transmis à Mistral AI pour transcription, puis supprimé.",
            "Résultats : transcription, intervenants et compte rendu pendant "
            f"{settings.result_retention_days} jours au maximum.",
        ],
        "purposes": [
            "Authentifier l’utilisateur.",
            "Obtenir et prouver le consentement des participants.",
            "Produire la transcription et le compte rendu demandés.",
        ],
        "legal_bases": [
            "Contrat : création et fonctionnement du compte.",
            "Consentement : enregistrement et analyse de la réunion.",
            "Obligation légale : réponse aux demandes d’exercice des droits.",
        ],
        "recipients": ["Organisateur de la réunion", "Mistral AI"],
        "processors": ["Mistral AI"],
        "rights": [
            "Retirer son consentement à tout moment.",
            "Accéder, exporter ou effacer ses données.",
            "Introduire une réclamation auprès de la CNIL.",
        ],
        "dpa_status": "À intégrer et faire valider avant la production.",
        "legal_configuration_complete": settings.legal_configured,
    }


@router.post("/legal/accept", status_code=204)
def accept_legal(
    payload: AgreementInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    save_agreements(user.id, payload, db)


@router.get("/privacy/export")
def export_data(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    recordings = db.exec(select(Recording).where(Recording.owner_id == user.id))
    meetings = db.exec(select(ConsentSession).where(ConsentSession.owner_id == user.id))
    agreements = db.exec(select(UserAgreement).where(UserAgreement.user_id == user.id))
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "created_at": user.created_at,
        },
        "agreements": [item.model_dump(exclude={"id", "user_id"}) for item in agreements],
        "meetings": [item.model_dump(exclude={"owner_id"}) for item in meetings],
        "recordings": [item.model_dump(exclude={"owner_id", "audio_path"}) for item in recordings],
    }


def delete_audio(recording: Recording) -> None:
    if not recording.audio_path:
        return
    path = Path(recording.audio_path).resolve()
    if path.is_relative_to(settings.audio_directory) and path.exists():
        path.unlink()


@router.delete("/privacy/account", status_code=204)
def delete_account(
    payload: DeleteAccountInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    if payload.confirmation != "DELETE":
        raise HTTPException(400, "Saisissez DELETE pour confirmer")

    recordings = list(db.exec(select(Recording).where(Recording.owner_id == user.id)))
    recording_ids = {item.id for item in recordings}
    meetings = list(db.exec(select(ConsentSession).where(ConsentSession.owner_id == user.id)))
    meeting_ids = {item.id for item in meetings}

    for link in list(db.exec(select(SessionRecording))):
        if link.recording_id in recording_ids or link.session_id in meeting_ids:
            db.delete(link)
    for consent in list(db.exec(select(ParticipantConsent))):
        if consent.session_id in meeting_ids:
            db.delete(consent)
        elif consent.email == user.email:
            consent.name = "Données effacées"
            consent.email = ""
            db.add(consent)
    for recording in recordings:
        report = db.exec(
            select(StructuredReport).where(StructuredReport.recording_id == recording.id)
        ).first()
        if report:
            db.delete(report)
        delete_audio(recording)
        db.delete(recording)
    for meeting in meetings:
        db.delete(meeting)
    for agreement in db.exec(select(UserAgreement).where(UserAgreement.user_id == user.id)):
        db.delete(agreement)
    for identity in db.exec(select(ExternalIdentity).where(ExternalIdentity.user_id == user.id)):
        db.delete(identity)
    db.delete(user)
    db.commit()
