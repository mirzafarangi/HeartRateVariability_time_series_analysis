"""
Session Validation System - Modular & Extensible
Version: 1.0.0
Date: 2025-08-07

Robust, modular validation system for HRV session data.
Designed to be easily extensible for future validation models,
quality scores, and advanced data validation requirements.
"""

import re
from typing import Dict, List, Any, Optional, Union
from uuid import UUID
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ValidationError:
    """Represents a single validation error with context"""
    
    def __init__(self, field: str, message: str, code: str = None, value: Any = None):
        self.field = field
        self.message = message
        self.code = code
        self.value = value
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'field': self.field,
            'message': self.message
        }
        if self.code:
            result['code'] = self.code
        if self.value is not None:
            result['received_value'] = str(self.value)
        return result

class ValidationResult:
    """Contains validation results and errors"""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.cleaned_data: Dict[str, Any] = {}
    
    def add_error(self, field: str, message: str, code: str = None, value: Any = None):
        self.errors.append(ValidationError(field, message, code, value))
    
    def add_warning(self, field: str, message: str, code: str = None, value: Any = None):
        self.warnings.append(ValidationError(field, message, code, value))
    
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.is_valid(),
            'errors': [error.to_dict() for error in self.errors],
            'warnings': [warning.to_dict() for warning in self.warnings],
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }

class BaseValidator:
    """Base class for all validators"""
    
    def validate(self, value: Any, field_name: str, context: Dict[str, Any] = None) -> ValidationResult:
        raise NotImplementedError("Subclasses must implement validate method")

class RequiredFieldValidator(BaseValidator):
    """Validates that required fields are present and not None"""
    
    def __init__(self, required_fields: List[str]):
        self.required_fields = required_fields
    
    def validate(self, data: Dict[str, Any], field_name: str = None, context: Dict[str, Any] = None) -> ValidationResult:
        result = ValidationResult()
        
        for field in self.required_fields:
            if field not in data:
                result.add_error(field, f"Field '{field}' is required", "MISSING_FIELD")
            elif data[field] is None:
                result.add_error(field, f"Field '{field}' cannot be null", "NULL_VALUE", data[field])
        
        return result

class UserIdValidator(BaseValidator):
    """Validates Supabase user ID format"""
    
    def validate(self, value: Any, field_name: str, context: Dict[str, Any] = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, str):
            result.add_error(field_name, "User ID must be a string", "INVALID_TYPE", value)
            return result
        
        # Length check
        if len(value) < 10 or len(value) > 50:
            result.add_error(field_name, "User ID must be between 10 and 50 characters", "INVALID_LENGTH", value)
            return result
        
        # Format check - allow letters, numbers, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', value):
            result.add_error(field_name, "User ID contains invalid characters", "INVALID_FORMAT", value)
            return result
        
        result.cleaned_data[field_name] = value
        return result

class SessionIdValidator(BaseValidator):
    """Validates session ID as strict UUID"""
    
    def validate(self, value: Any, field_name: str, context: Dict[str, Any] = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, str):
            result.add_error(field_name, "Session ID must be a string", "INVALID_TYPE", value)
            return result
        
        try:
            uuid_obj = UUID(value)
            result.cleaned_data[field_name] = str(uuid_obj)
        except ValueError:
            result.add_error(field_name, "Session ID must be a valid UUID", "INVALID_UUID", value)
        
        return result

class TagValidator(BaseValidator):
    """Validates session tags against canonical list"""
    
    VALID_TAGS = ['sleep', 'rest', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_duration', 'breath_workout']
    
    def validate(self, value: Any, field_name: str, context: Dict[str, Any] = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, str):
            result.add_error(field_name, "Tag must be a string", "INVALID_TYPE", value)
            return result
        
        if value not in self.VALID_TAGS:
            result.add_error(field_name, f"Tag must be one of: {', '.join(self.VALID_TAGS)}", "INVALID_TAG", value)
            return result
        
        result.cleaned_data[field_name] = value
        return result

class EventIdValidator(BaseValidator):
    """Validates event ID with flexible type conversion"""
    
    def validate(self, value: Any, field_name: str, context: Dict[str, Any] = None) -> ValidationResult:
        result = ValidationResult()
        
        # Allow None for non-sleep sessions
        if value is None:
            result.cleaned_data[field_name] = None
            return result
        
        # Try to convert to integer
        try:
            if isinstance(value, str):
                # Handle string representations
                if value.strip() == "":
                    result.cleaned_data[field_name] = None
                    return result
                event_id = int(value)
            elif isinstance(value, (int, float)):
                event_id = int(value)
            else:
                result.add_error(field_name, f"Event ID must be a number or string, got {type(value).__name__}", "INVALID_TYPE", value)
                return result
            
            # Validate positive integer
            if event_id <= 0:
                result.add_error(field_name, "Event ID must be a positive integer", "INVALID_VALUE", value)
                return result
            
            result.cleaned_data[field_name] = event_id
            
        except (ValueError, TypeError):
            result.add_error(field_name, f"Event ID must be convertible to a positive integer", "CONVERSION_ERROR", value)
        
        return result

class RRIntervalsValidator(BaseValidator):
    """Validates RR intervals data quality"""
    
    def __init__(self, min_count: int = 10, min_value: float = 200.0, max_value: float = 2000.0):
        self.min_count = min_count
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any, field_name: str, context: Dict[str, Any] = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, list):
            result.add_error(field_name, "RR intervals must be a list", "INVALID_TYPE", type(value).__name__)
            return result
        
        # Check minimum count
        if len(value) < self.min_count:
            result.add_error(field_name, f"RR intervals must contain at least {self.min_count} values", "INSUFFICIENT_DATA", len(value))
            return result
        
        # Validate each interval
        cleaned_intervals = []
        invalid_count = 0
        
        for i, interval in enumerate(value):
            try:
                # Convert to float
                interval_float = float(interval)
                
                # Check range
                if interval_float <= 0:
                    result.add_warning(field_name, f"RR interval at index {i} is not positive: {interval_float}", "NEGATIVE_VALUE", interval_float)
                    invalid_count += 1
                elif interval_float < self.min_value or interval_float > self.max_value:
                    result.add_warning(field_name, f"RR interval at index {i} outside normal range ({self.min_value}-{self.max_value}ms): {interval_float}", "OUT_OF_RANGE", interval_float)
                
                cleaned_intervals.append(interval_float)
                
            except (ValueError, TypeError):
                result.add_error(field_name, f"RR interval at index {i} is not a valid number: {interval}", "INVALID_NUMBER", interval)
                invalid_count += 1
        
        # Check if too many invalid intervals
        if invalid_count > len(value) * 0.1:  # More than 10% invalid
            result.add_error(field_name, f"Too many invalid RR intervals: {invalid_count}/{len(value)}", "HIGH_ERROR_RATE", invalid_count)
        
        result.cleaned_data[field_name] = cleaned_intervals
        return result

class SubtagValidator(BaseValidator):
    """Validates optional subtag field"""
    
    def validate(self, value: Any, field_name: str, context: Dict[str, Any] = None) -> ValidationResult:
        result = ValidationResult()
        
        if value is None:
            result.cleaned_data[field_name] = None
            return result
        
        if not isinstance(value, str):
            result.add_error(field_name, "Subtag must be a string", "INVALID_TYPE", value)
            return result
        
        if len(value) > 50:
            result.add_error(field_name, "Subtag must be 50 characters or less", "TOO_LONG", value)
            return result
        
        result.cleaned_data[field_name] = value.strip()
        return result

class SessionValidator:
    """Main session validator that orchestrates all validation"""
    
    def __init__(self):
        self.required_fields = ['user_id', 'session_id', 'tag', 'rr_intervals']
        self.validators = {
            'user_id': UserIdValidator(),
            'session_id': SessionIdValidator(),
            'tag': TagValidator(),
            'event_id': EventIdValidator(),
            'rr_intervals': RRIntervalsValidator(),
            'subtag': SubtagValidator()
        }
    
    def validate_session(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate complete session data
        
        Args:
            data: Session data dictionary from request
            
        Returns:
            ValidationResult with errors, warnings, and cleaned data
        """
        result = ValidationResult()
        
        logger.info(f"Validating session data: {list(data.keys())}")
        
        # Step 1: Check required fields
        required_validator = RequiredFieldValidator(self.required_fields)
        required_result = required_validator.validate(data)
        result.errors.extend(required_result.errors)
        
        # If required fields are missing, don't continue
        if not required_result.is_valid():
            logger.warning(f"Required field validation failed: {[e.field for e in required_result.errors]}")
            return result
        
        # Step 2: Validate each field individually
        for field_name, validator in self.validators.items():
            if field_name in data:
                field_result = validator.validate(data[field_name], field_name, data)
                result.errors.extend(field_result.errors)
                result.warnings.extend(field_result.warnings)
                result.cleaned_data.update(field_result.cleaned_data)
        
        # Step 3: Cross-field validation
        self._validate_cross_fields(data, result)
        
        # Step 4: Add any missing cleaned data for valid fields
        for field in self.required_fields:
            if field not in result.cleaned_data and field in data:
                result.cleaned_data[field] = data[field]
        
        # Add optional fields that passed validation
        for field in ['recorded_at', 'duration_minutes']:
            if field in data:
                result.cleaned_data[field] = data[field]
        
        logger.info(f"Validation complete: valid={result.is_valid()}, errors={len(result.errors)}, warnings={len(result.warnings)}")
        
        return result
    
    def _validate_cross_fields(self, data: Dict[str, Any], result: ValidationResult):
        """Validate relationships between fields"""
        
        # Sleep sessions should have event_id
        if data.get('tag') == 'sleep' and not data.get('event_id'):
            result.add_warning('event_id', 'Sleep sessions typically should have an event_id', "MISSING_SLEEP_EVENT")
        
        # Non-sleep sessions shouldn't have event_id
        if data.get('tag') != 'sleep' and data.get('event_id'):
            result.add_warning('event_id', 'Non-sleep sessions typically should not have an event_id', "UNEXPECTED_EVENT_ID")

# Convenience function for backward compatibility
def validate_session_data(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Legacy validation function for backward compatibility
    
    Returns:
        Dictionary of validation errors (empty if valid)
    """
    validator = SessionValidator()
    result = validator.validate_session(data)
    
    # Convert to legacy format
    errors = {}
    for error in result.errors:
        errors[error.field] = error.message
    
    return errors

# Enhanced validation function
def validate_session_enhanced(data: Dict[str, Any]) -> ValidationResult:
    """
    Enhanced validation function with full result details
    
    Returns:
        ValidationResult with errors, warnings, and cleaned data
    """
    validator = SessionValidator()
    return validator.validate_session(data)
