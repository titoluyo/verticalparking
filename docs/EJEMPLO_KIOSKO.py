# kiosko/app/routes.py - Extracto relevante
# Muestra: Coordinación del sistema, control del motor, y manejo de eventos MQTT

@bp.route("/guardar", methods=["POST"])
def guardar():
    """Procesa el almacenamiento de un vehículo."""
    # ... código de validación ...
    
    # Encuentra la siguiente cabina libre
    next_free_cabin = find_next_free_cabin_circular(next_cabin_in_circle, logger=current_app.logger)
    
    if next_free_cabin:
        next_free_cabin_presence = next_free_cabin.replace("CABINA-", "cabina-").lower()
        
        # Obtiene el servicio de control del motor
        motor_service = current_app.config.get("MOTOR_CONTROL_SERVICE")
        
        if motor_service:
            # Define callback para cuando la cabina llegue al piso
            def on_floor_reached(cabin_id: str, event_data: dict):
                """Callback cuando la cabina llega al nivel del piso."""
                try:
                    logger.info(f"Floor reached: {cabin_id} (distance={event_data.get('distance_mm')}mm)")
                    
                    # CRÍTICO: Detener el motor
                    stop_success = motor_service_ref.stop_motor(cabin_id_presence)
                    if not stop_success:
                        logger.error(f"Failed to stop motor for {cabin_id_presence}")
                    
                    # Activar la cabina
                    if presence_service_ref:
                        presence_service_ref.set_active_cabin(cabin_id_presence)
                        logger.info(f"Activated cabin: {cabin_id_presence}")
                        
                except Exception as e:
                    logger.error(f"Error in on_floor_reached callback: {e}")
                    # Medida de seguridad: intentar detener el motor
                    motor_service_ref.stop_motor(cabin_id_presence)
            
            # Registra el callback para la cabina esperada
            presence_service.register_floor_reached_callback(floor_callback)
            
            # Inicia el motor para mover la cabina al piso
            current_app.logger.info(f"Starting motor to move {next_free_cabin_presence} to floor...")
            motor_started = motor_service.start_motor(next_free_cabin_presence)
            
            if motor_started:
                # La cabina se está moviendo
                # El firmware detectará cuando llegue al piso y publicará el evento
                # El callback detendrá el motor automáticamente
                current_app.logger.info(f"Motor started for {next_free_cabin_presence}")
            else:
                current_app.logger.error(f"Failed to start motor for {next_free_cabin_presence}")
