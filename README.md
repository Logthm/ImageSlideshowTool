打包

``` python
pyinstaller -F -w slideshow_gui.py --icon=icon.ico --add-data "<你的venv>\Lib\site-packages\tkinterdnd2;tkinterdnd2/" --add-data "yahei.ttf;."
```
