ForwardingTool
==============

ForwardingTool is a simple GUI tool for easy setup of multiple SSH tunnels using the same jump server.
Soucre code is available on GitHub (https://github.com/Slarag/forwardingtool).
It was designed to work on Windows and Linux.

It heavily depends on the sshtunnel module (https://pypi.org/project/sshtunnel/)

Tunnel icons created by Freepik - Flaticon (https://www.flaticon.com/free-icons/tunnel)

Installation (Windows)
----------------------

1. Clone the repository to your local machine:

    ```C:\Users\slarag> git clone https://github.com/Slarag/forwardingtool.git```

2. Create a virtual environment for the project and activate it:

    ```C:\Users\slarag> cd forwardingtool```

    ```C:\Users\slarag\forwardingtool> python -m venv env```

    ```C:\Users\slarag\forwardingtool> env\Scripts\activate.bat```

3. Upgrade pip:

    ```(env) C:\Users\slarag\forwardingtool> python -m pip install --upgrade pip```

4. Install required package in the virtual environment:

    ```(env) C:\Users\slarag\forwardingtool> python -m pip install -r requirements.txt```

5. Run the tool:

    ```(env) C:\Users\slarag\forwardingtool> python main.py```

6. If you want to create an executable (=freeze the application with cx_freeze), run the following steps:

   ```(env) C:\Users\slarag\forwardingtool> python freeze.py build```

Installation (Linux)
--------------------

1. Clone the repository to your local machine:

    ```slarag@ubuntu> git clone https://github.com/Slarag/forwardingtool.git```

2. Create a virtual environment for the project and activate it:

    ```slarag@ubuntu: cd forwardingtool```

    ```slarag@ubuntu:~/forwardingtool> python -m venv env```

    ```slarag@ubuntu:~/forwardingtool> source env\bin\activate```

3. Upgrade pip:

    ```slarag@ubuntu:~/forwardingtool> python -m pip install --upgrade pip```

4. Install required package in the virtual environment:

    ```slarag@ubuntu:~/forwardingtool> python -m pip install -r requirements.txt```

5. Make "main.py" executable:

   ```slarag@ubuntu:~/forwardingtool> chmod +x main.py```

6. Run the tool:

    ```slarag@ubuntu:~/forwardingtool> python main.py```


Known Issues/Limitations
------------------------

- freeze.py script only available/tested for Windows OS