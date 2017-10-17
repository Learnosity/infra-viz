from flask import Flask, render_template, send_from_directory

app = Flask(__name__)

port=5000
host='0.0.0.0'

@app.route('/')
def index():
     return render_template('index.html')



@app.route('/data/<path:path>')
def send_data(path):
    return send_from_directory('data', path)


# @app.route('/static') is a magic inbuilt route


if __name__ == '__main__':
    app.run(debug=True, host=host, port=port)