"""
Modular Session Validator for HRV API
Clean architecture for session validation with extensible modules
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of session validation"""
    def __init__(self, is_valid: bool, errors: List[str] = None, warnings: List[str] = None, 
                 details: Dict = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.details = details or {}
    
    def to_dict(self):
        """Convert to dictionary for API response"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details
        }


class SessionValidator:
    """Modular session validator with clean architecture"""
    
    def __init__(self):
        self.validators = []
        self._register_default_validators()
    
    def _register_default_validators(self):
        """Register default validation modules"""
        # Duration validation removed - accept whatever iOS sends
        # Future validators can be added here:
        # self.validators.append(self._validate_hrv_quality)
        # self.validators.append(self._validate_artifact_detection)
    
    def validate(self, session_data: Dict) -> ValidationResult:
        """
        Run all validation modules on session data
        
        Args:
            session_data: Dictionary containing session information
                - duration_minutes: Duration from iOS (integer)
                - rr_intervals: List of RR intervals in milliseconds
                - tag: Session tag
                - subtag: Session subtag
                
        Returns:
            ValidationResult with detailed validation information
        """
        errors = []
        warnings = []
        details = {}
        
        # Basic session info for reporting (no validation)
        details['duration_ios_minutes'] = session_data.get('duration_minutes', 0)
        details['rr_interval_count'] = len(session_data.get('rr_intervals', []))
        
        # Calculate actual duration from RR intervals for info only
        rr_intervals = session_data.get('rr_intervals', [])
        if rr_intervals:
            duration_ms = sum(rr_intervals)
            details['duration_actual_seconds'] = round(duration_ms / 1000.0, 2)
            details['duration_actual_minutes'] = round(duration_ms / 60000.0, 2)
        
        # Add warning for very low RR count (but don't fail)
        if len(rr_intervals) < 10:
            warnings.append(f"Low RR interval count ({len(rr_intervals)}). Physiological metrics may be less reliable.")
        
        # Run any registered validators (currently none)
        for validator in self.validators:
            result = validator(session_data)
            if not result.is_valid:
                errors.extend(result.errors)
            warnings.extend(result.warnings)
            details.update(result.details)
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )
    

    
    def get_validation_report(self, session_data: Dict) -> Dict:
        """
        Generate a comprehensive validation report for UI display
        
        Returns a structured report suitable for iOS queue card display
        """
        result = self.validate(session_data)
        
        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_data.get('session_id', 'unknown'),
            "validation_result": result.to_dict(),
            "session_summary": {
                "tag": session_data.get('tag', 'unknown'),
                "subtag": session_data.get('subtag', 'unknown'),
                "event_id": session_data.get('event_id', 0),
                "duration_minutes": session_data.get('duration_minutes', 0),
                "rr_interval_count": len(session_data.get('rr_intervals', []))
            }
        }
        
        return report


# Singleton instance
session_validator = SessionValidator()
