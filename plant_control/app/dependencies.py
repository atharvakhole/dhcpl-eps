from fastapi import Depends, HTTPException, status


def get_plc_handler():
    """Dependency to get the global PLC handler instance"""
    from plant_control.app.main import plc_handler
    
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    return plc_handler


def get_health_service():
    """Dependency to get the global health service instance"""
    from plant_control.app.main import health_service
    
    if not health_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health service is not available"
        )
    
    return health_service


def get_procedure_executor():
    """Dependency to get the global procedure executor instance"""
    from plant_control.app.main import procedure_executor
    
    if not procedure_executor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Procedure executor not initialized"
        )
    
    return procedure_executor
