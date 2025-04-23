# CyTTY - PuTTY for CyBot

CyTTY is a replacement for PuTTY for CyBot, the primary embedded system we worked on for CPRE 2880 at Iowa State. CyTTY works with UART out of the box, includes voice recognition (you might have to bring your own microphones to the lab).


**If you're planning on using this for your final project, please see [License](#license).**

## Features

1. **Voice Controlled**: Now you don't have to type out curses to the CyBot, you could yell it out loud.
2. **Energy Threshold**: You can still make your mic work in noisy labs.
3. **UART Settings**: Go crazy with the UART configs during lab
4. **Text Input**: Sometimes voice recognition doesnt work (maybe your mic doesnt work, or you have a thick accent (*me too!*)), so I've added text input as fallback.
5. **Activity Log**: Inspired by OpenVPN, the Activity Log actually gives you readable status updates, also shows you the response from CyBot.

## Installation
1. Install Python
    - [Instructions](https://www.python.org/)
2. Clone this repository
    - `git clone https://github.com/Shad0wMazt3r/CyTTY`
    - `cd CyTTY/`
3. Install Requirements
    - `pip install -r requirements.txt`
    - **NOTE: There may be issues with pip depending upon your operating system. Please try the following commands in case the one given above does not work.**
    - `python -m pip install -r requirements.txt`
    - `python3 -m pip install -r requirements.txt`
4. Run CyTTY with the following command:
    -   `python cytty.py`


Boom! You should be able to run CyTTY now. Connect your computer to your CyBot using WiFi and enjoy the PuTTY free experience.
## License
You are free to modify, reuse, throw a brick at this code how ever you please.

 **BUT if you're using CyTTY or any part of this code for your final project, you must mention this repository and kindly request the TA for more extra credit points for Team SA-6.** 