# Project Title

Linkedin Bot Scripts

## Installing

 Python 3.4+
 selenium 3.12.0
 geckodriver[.exe]
 
 * Please put geckodriver[.exe] in /usr/bin/ in linux or similar on windows

	pip3 -r Bot-scripts/requirements.txt
 
## clone source first if the linkedin-bot folder is not there
	git clone https://github.com/high-sq-technology/linkedin-bot.git

## change to bot folder:

	cd linkedin-bot
	[git pull [if there is some updates]]
	

## Run Bot 
	cd Bot-scripts && soucce .env &&  python3 bot_mysql2.py 2>&1 >>bot.log &

## Run mini webserver: see its readme.txt in simplewerver


## Authors

* **Vasily Jin** - *main work* - [vajin1125](https://github.com/vajin1125)
