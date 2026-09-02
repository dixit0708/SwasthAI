from app.db.repository import BaseRepository

class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__("users")

class HealthProfileRepository(BaseRepository):
    def __init__(self):
        super().__init__("health_profiles")

class FamilyMemberRepository(BaseRepository):
    def __init__(self):
        super().__init__("family_members")

class MedicalRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__("medical_records")

class MedicalReportRepository(BaseRepository):
    def __init__(self):
        super().__init__("medical_reports")

class PredictionRepository(BaseRepository):
    def __init__(self):
        super().__init__("predictions")

class HealthMetricRepository(BaseRepository):
    def __init__(self):
        super().__init__("health_metrics")

class HealthGoalRepository(BaseRepository):
    def __init__(self):
        super().__init__("health_goals")

class MedicationRepository(BaseRepository):
    def __init__(self):
        super().__init__("medications")

class NotificationRepository(BaseRepository):
    def __init__(self):
        super().__init__("notifications")

class DoctorRepository(BaseRepository):
    def __init__(self):
        super().__init__("doctors")

class AppointmentRepository(BaseRepository):
    def __init__(self):
        super().__init__("appointments")

class AIConversationRepository(BaseRepository):
    def __init__(self):
        super().__init__("ai_conversations")

class AuditLogRepository(BaseRepository):
    def __init__(self):
        super().__init__("audit_logs")

# Instantiate repositories for easy import
user_repo = UserRepository()
health_profile_repo = HealthProfileRepository()
family_member_repo = FamilyMemberRepository()
medical_record_repo = MedicalRecordRepository()
medical_report_repo = MedicalReportRepository()
prediction_repo = PredictionRepository()
health_metric_repo = HealthMetricRepository()
health_goal_repo = HealthGoalRepository()
medication_repo = MedicationRepository()
notification_repo = NotificationRepository()
doctor_repo = DoctorRepository()
appointment_repo = AppointmentRepository()
ai_conversation_repo = AIConversationRepository()
audit_log_repo = AuditLogRepository()
