from flask import Flask, render_template, send_from_directory

app = Flask(__name__)

PORT=5001
HOST='0.0.0.0'

@app.route('/')
def index():
    ''' Render the index page '''
    return render_template('index.html')


@app.route('/data/<path:path>')
def send_data(path):
    ''' Method to handle static files to be returned '''
    return send_from_directory('data', path)


# @app.route('/static') is a magic inbuilt route


if __name__ == '__main__':
    app.run(debug=True, host=HOST, port=PORT)
