import os
import yaml
import logging
import socket
import signal
import traceback
from colorama import Fore, Style
from colorama import init
init(autoreset=True)  # Initialize colorama for automatic reset of colors
import sys
OSPP_DEAULT_LOG_FILE = 'ospp.log'

#-------FOR TESTING ONLY-------------------
import subprocess

def create_ip_alias(interface, ip_address, subnet_mask):
    """Creates an IP alias on the specified network interface.

    Args:
        interface (str): The network interface name (e.g., "en0").
        ip_address (str): The IP address for the alias.
        subnet_mask (str): The subnet mask for the alias (e.g., "255.255.255.0").
    """
    command = f"sudo ifconfig {interface} alias {ip_address} netmask {subnet_mask}"
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"IP alias {ip_address} created on interface {interface}.")
    except subprocess.CalledProcessError as e:
        print(f"Error creating IP alias: {e}")

def delete_ip_alias(interface, ip_address):
    """Deletes an IP alias from the specified network interface.

    Args:
        interface (str): The network interface name (e.g., "en0").
        ip_address (str): The IP address of the alias to delete.
    """
    command = f"sudo ifconfig {interface} -alias {ip_address}"
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"IP alias {ip_address} deleted from interface {interface}.")
    except subprocess.CalledProcessError as e:
        print(f"Error deleting IP alias: {e}")
#-----FOR TESTING ONLY-------------------

#--------------------------------------------------------------
#Function to setup signal traps. We need to know when user hit CTRL-C
def signal_handler(sig, frame):
        print('You pressed Ctrl+C!')
        print("\nSIGINT received. Shutting down gracefully...")
        logger.info("SIGINT received. Shutting down gracefully...")
        sockets = []  # List to store all socket connections
        for s in sockets:
            try:
                s.shutdown(socket.SHUT_RDWR)  # Disable further sends and receives
                s.close()
            except OSError as e:
             print(f"Error closing socket: {e}")

        sys.exit(0)

    #singal.pause()
    #return
#end of setup_signal_handling():
#------------------------------------------------------------------------------
#--------------------------------------------------------------
# Set up logging configuration
def setup_logging(log_file=OSPP_DEAULT_LOG_FILE):
    logger = logging.getLogger()    # Create a logger instance
    logger.setLevel(logging.INFO) #Set the logging level to INFO

    console_handler = logging.StreamHandler()   # Create a console handler and set its level to INFO
    console_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file) # Create a file handler to log messages to a file and set its level to INFO
    file_handler.setLevel(logging.INFO)

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - \033[94m%(message)s\033[0m')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add both handlers to the logger
    #logger.addHandler(console_handler)  #Rem to stop**! console handler to the logger
    logger.addHandler(file_handler) # Add the file handler to the logger

    return logger
#End of setup_logging()
#--------------------------------------------------------


logger = setup_logging (OSPP_DEAULT_LOG_FILE)  # Set up logging configuration

#--------------------------------------------------------------
# Function to print error details
def print_error_details(msg):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback_details = traceback.extract_tb(exc_traceback)
    filename, line_number, function_name, text = traceback_details[-1]

    print(f"{Fore.LIGHTRED_EX}{msg}", flush=True)
    print(f"{Fore.LIGHTRED_EX}[D] {Fore.LIGHTCYAN_EX}Module:{Fore.LIGHTBLACK_EX}[{__name__}] {Fore.LIGHTCYAN_EX}File:{Fore.LIGHTBLACK_EX}[{filename}] {Fore.LIGHTCYAN_EX}Line:{Fore.LIGHTBLACK_EX}[{line_number}] {Fore.LIGHTCYAN_EX}Function:{Fore.LIGHTBLACK_EX}[{function_name}]", flush=True)

    #print(f"{Fore.RED}Error: {e}", flush=True)
    #print(f"{Fore.RED}Error occurred in file: {filename}", flush=True)  
    #print(f"{Fore.RED}Line number: {line_number}", flush=True)
    #print(f"{Fore.RED}Text: {text}", flush=True)
    #print(f"{Fore.RED}Function name: {function_name}\n", flush=True)
    #print ("--------------------------------------", flush=True)
    # Log the error details
    logging.error(f"Error occurred in file: {filename}: {line_number} in function: {function_name}")
#End of print_error_details()
# -------------------------------------------------------------

#--------------------------------------------------------------
def DLevel(DEBUG_LEVEL=0):
    import sys
    import sys
    frame = sys._getframe(1)  # Caller frame
    func_name = frame.f_code.co_name
    line_no = frame.f_lineno
    #return f"[D:{DEBUG_LEVEL}] Function:[{func_name}] Line:[{line_no}]"
    data =[]
    """Set the debug level"""
    if DEBUG_LEVEL >= 5:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}][Func:{func_name}]' #, end=line:[{sys._getframe().f_lineno}]"
    
    if DEBUG_LEVEL >= 4:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}]'
    if DEBUG_LEVEL >= 3:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}]'
    if DEBUG_LEVEL == 2:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}]'
    if DEBUG_LEVEL == 1:
        return f'[D:{Fore.LIGHTRED_EX}{DEBUG_LEVEL}{Fore.RESET}]'
    
#End of DLevel()
#--------------------------------------------------------------