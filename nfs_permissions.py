#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetApp ONTAP SVM Creation and Configuration Script

This script automates the creation and configuration of Storage Virtual Machines (SVMs)
on NetApp ONTAP systems using the NetApp ONTAP REST API Python Client Library.

Features:
    - SVM creation with custom parameters
    - FCP service configuration
    - Multiple network interfaces (FCP LIFs)
    - Management interface creation
    - Protocol configuration
    - Comprehensive error handling and validation

Requirements:
    - NetApp ONTAP 9.6+
    - Python 3.7+
    - netapp-ontap library
    - PyYAML library

Author: NetApp ONTAP Automation
Version: 1.0.0
"""

# ============================================================================
# IMPORTS
# ============================================================================
from netapp_ontap import config, HostConnection, NetAppRestError
from netapp_ontap.resources import Cluster, Svm, EmsEvent, Account, Role, RolePrivilege
import yaml
import json
import os
from datetime import datetime


# ============================================================================
# SCRIPT INITIALIZATION
# ============================================================================
print("\n" + "="*70)
print("  NetApp ONTAP FCP SVM Creation Script")
print("  Using NetApp ONTAP Python Client Library")
print("="*70)
print("\n[*] Initializing SVM creation workflow...")


# ============================================================================
# YAML CONFIGURATION FUNCTION
# ============================================================================

def config_loader(path="config.yaml"):
    """
    Carga la configuración desde un archivo YAML con validación completa
    
    Lee el archivo de configuración y valida que contenga las secciones
    necesarias para crear una SVM en NetApp ONTAP.
    
    Args:
        path: Ruta al archivo de configuración (por defecto 'config.yaml')
    
    Returns:
        dict: Diccionario con la configuración cargada, o None si falla
    """
    try:
        print(f"[+] Config.yaml loader: {path}")
        
        # Abrir y leer el contenido del archivo YAML
        with open(path, 'r', encoding='utf-8') as file:
            config_data = yaml.safe_load(file)
        
        # VALIDACIONES
        # Validar que el archivo no esté vacío
        if config_data is None:
            print(f"[ERROR] File '{path}' is empty or doen't contain valid YAML")
            return None
        
        # Validar estructura: debe contener seccion 'cluster'
        if 'cluster' not in config_data:
            print(f"[ERROR]Incomplete configuration: missing 'cluster' section")
            return None
        
        # Validar estructura: debe contener seccion 'svm'
        if 'svm' not in config_data:
            print(f"[ERROR] Incomplete configuration: missing 'svm' section")
            return None
        
        print(f"[+] Configuration loaded successfully")

        # Mostrar resumen de la configuración cargada
        print(f"[+] Target cluster: {config_data['cluster'].get('host', 'N/A')}")
        print(f"[+] SVM to create: {config_data['svm'].get('name', 'N/A')}")
        
        return config_data
    
    # CONTROL DE ERRORES
    except FileNotFoundError:
        print(f"[ERROR] File not found: {path}")
        print(f"[ERROR] Please check the path and try again")
        return None
    
    except yaml.YAMLError as e:
        print(f"[ERROR] Invalid YAML format in '{path}'")
        print(f"[ERROR] Detail: {str(e)}")
        return None
    
    except PermissionError:
        print(f"[ERROR] Insufficient permissions to read: {path}")
        return None
    
    except Exception as e:
        print(f"[ERROR] Unexpected failure: {type(e).__name__}")
        print(f"[ERROR] Message: {str(e)}")
        return None


# ============================================================================
# SAVE TO LOG FUNCTION
# ============================================================================

def save_to_log(operation_name, data):
    """
    Guarda datos en un archivo JSON dentro de la carpeta logs/ con timestamp
    
    Args:
        operation_name (str): Nombre de la operación (ej: 'create_svm', 'fcp_create')
        data (dict): Datos a guardar (normalmente el show de la cabina)
    
    Returns:
        str: Ruta del archivo creado
    """
    try:
        # Crear carpeta logs si no existe
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        # Generar timestamp: YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Nombre del archivo: operation_YYYYMMDD_HHMMSS.json
        filename = f"{logs_dir}/{operation_name}_{timestamp}.json"
        
        # Guardar en formato JSON
        with open(filename, 'w', encoding='utf-8') as log_file:
            json.dump(data, log_file, indent=2, ensure_ascii=False)
        
        print(f"[LOG] Saved to: {filename}")
        return filename
    
    except Exception as e:
        print(f"[WARNING] Could not save log: {str(e)}")
        return None


# ============================================================================
# CLUSTER CONNECTION FUNCTION
# ============================================================================

def cluster_connection(cluster_config):
    """
    Establece conexión con la cabina NetApp ONTAP y verifica acceso
    
    Conecta con el cluster usando las credenciales proporcionadas y realiza
    una consulta de prueba para validar que el acceso es correcto.
    
    Args:
        cluster_config: Diccionario con claves 'host', 'username', 'password'
    
    Returns:
        bool: True si conexión exitosa, False si hay errores
    """
    try:
        print(f"\n[*] Establishing connection to cluster: {cluster_config.get('host', 'N/A')}")
        
        # Validar que existan todos los campos necesarios
        required_keys = ['host', 'username', 'password']
        # Itera por cada clave requerida y guarda en una lista las que faltan
        missing_keys = [key for key in required_keys if key not in cluster_config]
        
        if missing_keys:
            print(f"[ERROR] Missing required fields in cluster config: {', '.join(missing_keys)}")
            return False
        
        # Establecer conexión con la cabina
        config.CONNECTION = HostConnection(
            cluster_config['host'],
            username=cluster_config['username'],
            password=cluster_config['password'],
            verify=False 
        )
        
        # Verificar acceso haciendo una consulta al cluster
        cluster_info = Cluster()
        cluster_info.get()
        
        print(f"[+] Connection successful!")
        print(f"[+] Cluster name: {cluster_info.name}")
        print(f"[+] ONTAP version: {cluster_info.version.full}")

        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp REST API error")
        print(f"[ERROR] HTTP status: {error.status_code}")
        
        # Detallar el tipo de error según el código HTTP
        if error.status_code == 401:
            print(f"[ERROR] Authentication failed")
            print(f"[ERROR] Invalid username or password for user '{cluster_config.get('username')}'")
        elif error.status_code == 403:
            print(f"[ERROR] Forbidden - User lacks required permissions")
        elif error.status_code == 404:
            print(f"[ERROR] Resource not found - Check cluster URL")
        else:
            print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        
        return False
    
    except KeyError as e:
        print(f"[ERROR] Configuration error - Missing key: {str(e)}")
        return False
    
    except ConnectionError:
        print(f"[ERROR] Cannot reach host '{cluster_config.get('host')}'")
        print(f"[ERROR] Check network connectivity and hostname/IP")
        return False
    
    except TimeoutError:
        print(f"[ERROR] Connection timeout to '{cluster_config.get('host')}'")
        print(f"[ERROR] Cluster is not responding")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {type(e).__name__}")
        print(f"[ERROR] Message: {str(e)}")
        return False


# ============================================================================
# NFS LOGIN PERMISSIONS FUNCTION
# ============================================================================

def create_login_roles(roles_config):
    """
    Crea roles de login en la SVM con permisos específicos de comando
    
    Esta función itera sobre una lista de configuraciones de roles y crea
    cada uno usando la API REST de NetApp ONTAP. Cada rol puede tener
    diferentes niveles de acceso a directorios de comandos específicos.
    
    Equivalente CLI: security login role create -role <name> -vserver <svm> 
                     -cmddirname <path> -access <level>
    
    Args:
        roles_config (list): Lista de diccionarios con configuración de roles.
                             Cada diccionario debe contener:
                             - role: Nombre del rol (ej: 'telcoedgeadmin')
                             - svm: Nombre de la SVM
                             - cmddirname: Directorio de comando (ej: 'volume file clone')
                             - access: Nivel de acceso ('readonly', 'all', 'none')
    
    Returns:
        bool: True si todos los roles se crearon exitosamente, False si hubo errores
    """
    try:
        print(f"\n[*] Creating login roles from configuration...")
        
        # Validar que se proporcionó una lista
        if not roles_config or not isinstance(roles_config, list):
            print(f"[ERROR] Invalid roles configuration - expecting a list")
            return False
        
        print(f"[+] Found {len(roles_config)} role(s) to create")
        
        # Contador de éxitos y fallos
        success_count = 0
        failed_count = 0
        created_roles = []
        
        # AGRUPAR roles por (role_name, svm) para crear una sola vez con múltiples privilegios
        from collections import defaultdict
        grouped_roles = defaultdict(list)
        
        for role_entry in roles_config:
            # Validar campos requeridos
            required_fields = ['role', 'svm', 'cmddirname', 'access']
            missing_fields = [field for field in required_fields if field not in role_entry]
            
            if missing_fields:
                print(f"[WARNING] Skipping role entry - missing fields: {', '.join(missing_fields)}")
                failed_count += 1
                continue
            
            # Agrupar por (nombre_rol, svm)
            key = (role_entry['role'], role_entry['svm'])
            grouped_roles[key].append({
                'cmddirname': role_entry['cmddirname'],
                'access': role_entry['access']
            })
        
        # Iterar sobre cada grupo de roles
        for (role_name, svm_name), privileges_list in grouped_roles.items():
            try:
                print(f"\n[*] Creating role '{role_name}' for SVM '{svm_name}'...")
                print(f"    Privileges to configure: {len(privileges_list)}")
                
                # Construir lista de privilegios para la API
                # Cada privilegio necesita 'path' (cmddirname) y 'access'
                privileges = []
                for priv in privileges_list:
                    privilege_obj = {
                        'path': priv['cmddirname'],
                        'access': priv['access']
                    }
                    privileges.append(privilege_obj)
                    print(f"    - Command: '{priv['cmddirname']}' -> Access: '{priv['access']}'")
                
                # Crear objeto Role con la configuración
                new_role = Role()
                new_role.name = role_name
                new_role.owner = {'name': svm_name}  # SVM owner
                new_role.privileges = privileges
                
                # POST: Enviar petición de creación a la cabina
                print(f"[*] Sending role creation request to NetApp cluster...")
                new_role.post()
                
                print(f"[SUCCESS] Role '{role_name}' created successfully in SVM '{svm_name}'")
                success_count += 1
                
                # Guardar información del rol creado
                created_roles.append({
                    'role_name': role_name,
                    'svm': svm_name,
                    'privileges': privileges,
                    'status': 'created'
                })
                
            except NetAppRestError as error:
                print(f"[ERROR] Failed to create role '{role_name}' in SVM '{svm_name}'")
                print(f"[ERROR] HTTP Status: {error.status_code}")
                
                # Manejar códigos de error específicos
                if error.status_code == 409:
                    print(f"[ERROR] Role already exists")
                elif error.status_code == 404:
                    print(f"[ERROR] SVM '{svm_name}' not found")
                else:
                    if error.http_err_response and error.http_err_response.http_response:
                        print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
                
                failed_count += 1
                created_roles.append({
                    'role_name': role_name,
                    'svm': svm_name,
                    'privileges': privileges,
                    'status': 'failed',
                    'error': str(error)
                })
            
            except Exception as e:
                print(f"[ERROR] Unexpected error creating role '{role_name}': {type(e).__name__}")
                print(f"[ERROR] Details: {str(e)}")
                failed_count += 1
        
        # SUMMARY: Mostrar resumen de la operación
        print(f"\n{'='*70}")
        print(f"  Role Creation Summary")
        print(f"{'='*70}")
        print(f"Total roles processed: {len(grouped_roles)}")
        print(f"Successfully created:  {success_count}")
        print(f"Failed:                {failed_count}")
        print(f"{'='*70}\n")
        
        # Guardar log con timestamp
        log_data = {
            'operation': 'create_login_roles',
            'total_processed': len(grouped_roles),
            'successful': success_count,
            'failed': failed_count,
            'roles': created_roles
        }
        save_to_log('role_creation', log_data)
        
        # Retornar True solo si todos fueron exitosos
        return failed_count == 0
    
    except Exception as e:
        print(f"[ERROR] Unexpected error in create_login_roles: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        return False



# ============================================================================
# EVENT LOG RETRIEVAL FUNCTION
# ============================================================================

def get_event_logs(max_records=100):
    """
    Obtiene los logs de eventos del sistema NetApp ONTAP
    
    Args:
        max_records: Número máximo de eventos a recuperar (default: 100)
    
    Returns:
        bool: True si se obtuvieron exitosamente, False si hubo error
    """
    try:
        print(f"\n[*] Retrieving event logs from cluster...")
        
        # GET: Obtener eventos del sistema desde la cabina
        events_list = []
        ems_events = EmsEvent.get_collection(max_records=max_records)
        
        for event in ems_events:
            event_data = {
                'index': event.index if hasattr(event, 'index') else 'N/A',
                'time': str(event.time) if hasattr(event, 'time') else 'N/A',
                'node': event.node.name if hasattr(event, 'node') and event.node else 'N/A',
                'severity': event.message.severity if hasattr(event, 'message') and hasattr(event.message, 'severity') else 'N/A',
                'event': event.message.name if hasattr(event, 'message') and hasattr(event.message, 'name') else 'N/A'
            }
            events_list.append(event_data)
        
        event_log_data = {
            'total_events': len(events_list),
            'max_records_requested': max_records,
            'events': events_list
        }
        
        # SHOW: Mostrar información como "event log show"
        print(f"\n{'='*110}")
        print(f"  Event Log Show")
        print(f"{'='*110}")
        print(f"{'Index':<8} {'Time':<25} {'Node':<20} {'Severity':<12} {'Event':<40}")
        print(f"{'-'*8} {'-'*25} {'-'*20} {'-'*12} {'-'*40}")
        
        for evt in events_list[:20]:  # Mostrar solo los primeros 20 en pantalla
            print(f"{str(evt['index']):<8} {evt['time']:<25} {evt['node']:<20} {evt['severity']:<12} {evt['event']:<40}")
        
        if len(events_list) > 20:
            print(f"... ({len(events_list) - 20} more events)")
        
        print(f"\nTotal events retrieved: {len(events_list)}")
        print(f"{'='*110}\n")
        
        # Guardar en log con timestamp
        save_to_log('event_logs', event_log_data)
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error during event log retrieval")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        if error.http_err_response and error.http_err_response.http_response:
            print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        else:
            print(f"[ERROR] Details: {str(error)}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error during event log retrieval: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        return False

# ============================================================================
# CALLING WORKFLOW
# ============================================================================

# CONFIG YAML LOADER
# Cargar la configuración desde el archivo YAML
config_data = config_loader()

# Verificar que la configuración se cargó exitosamente
if config_data is None:
    print("\n[ERROR] Cannot continue without valid configuration")
    print("[ERROR] Check the config.yaml file and try again")
    exit(1)
else:
    print("\n[SUCCESS] Configuration loaded - Proceeding with pre-checks")

# CLUSTER CONNECTION CHECK
# Establecer conexión y verificar acceso a la cabina NetApp
if not cluster_connection(config_data['cluster']):
    print("\n[ERROR] Failed to connect to NetApp cluster")
    print("[ERROR] Fix connection issues before continuing")
    exit(1)

print("\n[+] All pre-checks passed - Ready to create users")

# NFS LOGIN PERMISSIONS
# Crear roles de login con permisos específicos desde config.yaml
print(f"[DEBUG] Keys in config_data: {list(config_data.keys())}")
print(f"[DEBUG] 'roles' in config_data: {'roles' in config_data}")
if 'roles' in config_data:
    print(f"[DEBUG] config_data['roles'] = {config_data['roles']}")
    print(f"[DEBUG] Type: {type(config_data['roles'])}")
    print(f"[DEBUG] Length: {len(config_data['roles']) if config_data['roles'] else 0}")

if 'roles' in config_data and config_data['roles']:
    print("\n[*] Starting role creation process...")
    if create_login_roles(config_data['roles']):
        print("\n[SUCCESS] All login roles created successfully!")
    else:
        print("\n[WARNING] Some roles failed to create (check logs for details)")
else:
    print("\n[WARNING] No roles configured in config.yaml - Skipping role creation")

'''
# LOGS BACKUP
# Obtener event logs de la cabina como backup
if get_event_logs(max_records=100):
    print("\n[SUCCESS] Event logs backup completed!")
else:
    print("\n[WARNING] Event logs backup failed (non-critical)")
'''