# docker_manager.py
import os
import subprocess
import pathlib
from typing import Dict
import docker
import zipfile, os, pathlib, shutil, textwrap

# Cambiar este path a la ruta donde se guardarán los servicios de los usuarios
# Change this path to the path where the user's services will be saved
BASE_PATH = pathlib.Path("/home/christian/Proyectos/ProyectoClase/apiProyecto/IntermediateAPI_PROYECTO_ASIR/API_Intermediate/srv")  # cámbialo si necesitas otra raíz

class DockerManager:
    """
    Orquesta la creación de contenedores sueltos y stacks docker-compose
    a partir de la información recibida por la API. 

    Orchestrates the creation of standalone containers and docker-compose stacks
    based on information received from the API.
    """

    def __init__(self):
        # Cliente docker api de alto nivel
        # high level docker api client
        self.client = docker.from_env()
        self.low_level = docker.APIClient()
        self._ensure_network()

    # ---------- utilidades internas ----------
    # ---------- internal utilities ----------

    # Creamos las carpetas necesarias
    # Data para los archivos del usuario de la página
    # filebrowser_data para el archivo de la base de datos de filebrowser
    def _ensure_path(self, user: str, project: str) -> pathlib.Path:
        target = BASE_PATH / user / project
        (target / "data").mkdir(parents=True, exist_ok=True)
        (target / "filebrowser_data").mkdir(exist_ok=True)
        return target

    def _run_once_container(
        self, image: str, cmd: str | list[str], volumes: Dict[str, dict]
    ):
        """
        Ejecuta un contenedor efímero (`--rm`) y espera a que termine
        (equivalente a tus dos comandos de `docker run --rm …`).

        Run a temporary container (`--rm`) and wait for it to finish
        (equivalent to your two `docker run --rm …` commands).
        """
        self.client.containers.run(
            image=image,
            command=cmd,
            remove=True,
            volumes=volumes,
        )

    # Creamos la red si no existe
    # Create the network if it doesn't exist
    def _ensure_network(self):
        if not any(n.name == "caddy_net" for n in self.client.networks.list()):
            self.client.networks.create("caddy_net", driver="bridge")

    # Descomprime el zip de manera segura
    # Safely extract the zip
    def _safe_extract(self, zf: zipfile.ZipFile, dest: pathlib.Path):
        for member in zf.infolist():
            member_path = dest / member.filename
            if not str(member_path.resolve()).startswith(str(dest.resolve())):
                raise RuntimeError("Zip traversal detected!")
        zf.extractall(dest)

    # ---------- casos públicos ----------
    # ---------- public cases ----------

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Stack estático con filebrowser
    # Static stack with filebrowser
    def deploy_static_with_filebrowser(
        # TODO: Generar contraseña aleatoria o usar la que el usuario elija
        # TODO: Generate a random password or use the one the user chooses
        self, user: str, project: str, zip_path: str | None, admin_pass: str = "admin123"
    ):
        """
        Crea el stack en la carpeta del usuario.
        Creates the stack in the user's folder.
        """
        target = self._ensure_path(user, project)

        # 0) Descomprimir el zip
        if zip_path:
            print(f"Extracting {zip_path} → {target/'data'}")
            with zipfile.ZipFile(zip_path) as zf:
                self._safe_extract(zf, target / "data")
            os.remove(zip_path)  # limpia tmp | Clear tmp

        # 1) Inicializar DB
        # Initialize DB
        self._run_once_container(
            "filebrowser/filebrowser",
            ["config", "init", "--database", "/srv/filebrowser.db"],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )

        # 2) Crear usuario admin
        # Create admin user
        self._run_once_container(
            "filebrowser/filebrowser",
            [
                "users",
                "add",
                "admin",
                admin_pass,
                "--database",
                "/srv/filebrowser.db",
                "--perm.admin",
            ],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )

        # 3) Escribir docker-compose.yml
        # Puse el dominio mio personal, cambiar al dominio de clase cloudfaster.com
        # Write docker-compose.yml
        # I used my personal domain, change to cloudfaster.com
        compose_text = textwrap.dedent(f"""
        services:
          httpd:
            image: httpd:latest
            networks:
              - caddy_net
            volumes:
              - "./data:/usr/local/apache2/htdocs/"
            labels:
              caddy: "{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 80}}}}"
            restart: always

          filebrowser:
            image: filebrowser/filebrowser:latest
            networks:
              - caddy_net
            labels:
              caddy: "fb-{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 80}}}}"
            volumes:
              - "./filebrowser_data/filebrowser.db:/database.db"
              - "./data:/srv"
            command: --database /database.db
            restart: always

        networks:
          caddy_net:
            external: true
        """)
        (target / "docker-compose.yml").write_text(compose_text)

        # 4) Levantar servicios con docker compose v2
        subprocess.run(
            ["docker", "compose", "up", "-d"], cwd=target, check=True
        )
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Stack PHP con filebrowser
    # PHP stack with filebrowser
    def deploy_php_with_filebrowser(
        self, user: str, project: str, zip_path: str | None, admin_pass: str = "admin123"
    ):
        """
        Crea el stack PHP con filebrowser en la carpeta del usuario.
        Creates the PHP stack with filebrowser in the user's folder.
        """
        target = self._ensure_path(user, project)

        # 0) Descomprimir el zip
        if zip_path:
            print(f"Extracting {zip_path} → {target/'data'}")
            with zipfile.ZipFile(zip_path) as zf:
                self._safe_extract(zf, target / "data")
            os.remove(zip_path)  # limpia tmp | Clear tmp

        # 1) Inicializar DB
        # Initialize DB
        self._run_once_container(
            "filebrowser/filebrowser",
            ["config", "init", "--database", "/srv/filebrowser.db"],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )

        # 2) Crear usuario admin
        # Create admin user
        self._run_once_container(
            "filebrowser/filebrowser",
            [
                "users",
                "add",
                "admin",
                admin_pass,
                "--database",
                "/srv/filebrowser.db",
                "--perm.admin",
            ],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )

        # 3) Escribir docker-compose.yml para PHP
        # Write docker-compose.yml for PHP
        compose_text = textwrap.dedent(f"""
        services:
          php-apache:
            image: php:8.3-apache
            networks:
              - caddy_net
            volumes:
              - "./data:/var/www/html"
            labels:
              caddy: "{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 80}}}}"
            restart: always

          filebrowser:
            image: filebrowser/filebrowser:latest
            networks:
              - caddy_net
            labels:
              caddy: "fb-{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 80}}}}"
            volumes:
              - "./filebrowser_data/filebrowser.db:/database.db"
              - "./data:/srv"
            command: --database /database.db
            restart: always

        networks:
          caddy_net:
            external: true
        """)
        (target / "docker-compose.yml").write_text(compose_text)

        # 4) Levantar servicios con docker compose v2
        subprocess.run(
            ["docker", "compose", "up", "-d"], cwd=target, check=True
        )
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Stack Laravel con filebrowser
    # Laravel stack with filebrowser
    def deploy_laravel_with_filebrowser(
        self, user: str, project: str, zip_path: str | None, admin_pass: str = "admin123"
    ):
        """
        Crea el stack Laravel con filebrowser en la carpeta del usuario.
        Creates the Laravel stack with filebrowser in the user's folder.
        """
        target = self._ensure_path(user, project)

        # 0) Descomprimir el zip si se proporciona
        # Extract zip if provided
        if zip_path:
            print(f"Extracting {zip_path} → {target/'data'}")
            with zipfile.ZipFile(zip_path) as zf:
                self._safe_extract(zf, target / "data")
            os.remove(zip_path)  # limpia tmp | Clear tmp
        
        # 1) Inicializar DB para filebrowser
        # Initialize DB for filebrowser
        self._run_once_container(
            "filebrowser/filebrowser",
            ["config", "init", "--database", "/srv/filebrowser.db"],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )

        # 2) Crear usuario admin para filebrowser
        # Create admin user for filebrowser
        self._run_once_container(
            "filebrowser/filebrowser",
            [
                "users",
                "add",
                "admin",
                admin_pass,
                "--database",
                "/srv/filebrowser.db",
                "--perm.admin",
            ],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )
        
        # 3) Crear proyecto Laravel si no se proporcionó un zip
        # Create Laravel project if no zip provided
        if not zip_path:
            print(f"Creating Laravel project in {target/'data'}")
            self._run_once_container(
                "composer",
                ["create-project", "laravel/laravel", "."],
                {str(target / "data"): {"bind": "/app", "mode": "rw"}},
            )

        # 4) Escribir docker-compose.yml para Laravel
        # Write docker-compose.yml for Laravel
        compose_text = textwrap.dedent(f"""
        services:
          laravel:
            image: php:8.3-cli
            networks:
              - caddy_net
            working_dir: /var/www
            volumes:
              - "./data:/var/www"
            command: php artisan serve --host=0.0.0.0 --port=8000
            labels:
              caddy: "{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 8000}}}}"
            restart: always

          composer:
            image: composer:latest
            working_dir: /var/www
            volumes:
              - "./data:/var/www"
            command: composer install
            depends_on:
              - laravel

          filebrowser:
            image: filebrowser/filebrowser:latest
            networks:
              - caddy_net
            labels:
              caddy: "fb-{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 80}}}}"
            volumes:
              - "./filebrowser_data/filebrowser.db:/database.db"
              - "./data:/srv"
            command: --database /database.db
            restart: always

        networks:
          caddy_net:
            external: true
        """)
        (target / "docker-compose.yml").write_text(compose_text)

        # 5) Levantar servicios con docker compose v2
        subprocess.run(
            ["docker", "compose", "up", "-d"], cwd=target, check=True
        )
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Stack Node.js con filebrowser
    # Node.js stack with filebrowser
    def deploy_nodejs_with_filebrowser(
        self, user: str, project: str, zip_path: str | None, admin_pass: str = "admin123"
    ):
        """
        Crea el stack Node.js con filebrowser en la carpeta del usuario.
        Creates the Node.js stack with filebrowser in the user's folder.
        """
        target = self._ensure_path(user, project)

        # 0) Descomprimir el zip si se proporciona
        # Extract zip if provided
        if zip_path:
            print(f"Extracting {zip_path} → {target/'data'}")
            with zipfile.ZipFile(zip_path) as zf:
                self._safe_extract(zf, target / "data")
            os.remove(zip_path)  # limpia tmp | Clear tmp
        
        # 1) Inicializar DB para filebrowser
        # Initialize DB for filebrowser
        self._run_once_container(
            "filebrowser/filebrowser",
            ["config", "init", "--database", "/srv/filebrowser.db"],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )

        # 2) Crear usuario admin para filebrowser
        # Create admin user for filebrowser
        self._run_once_container(
            "filebrowser/filebrowser",
            [
                "users",
                "add",
                "admin",
                admin_pass,
                "--database",
                "/srv/filebrowser.db",
                "--perm.admin",
            ],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )
        
        # 3) Crear proyecto Node.js si no se proporcionó un zip
        # Create Node.js project if no zip provided
        if not zip_path:
            print(f"Creating Node.js project in {target/'data'}")
            try:
                # Primero asegurarse que el directorio esté vacío
                # First ensure directory is empty
                if (target / "data").exists() and any((target / "data").iterdir()):
                    shutil.rmtree(target / "data")
                    (target / "data").mkdir(exist_ok=True)
                
                # Crear package.json básico e instalar express y nodemon
                # Create basic package.json and install express and nodemon
                (target / "data" / "package.json").write_text(textwrap.dedent('''
                {
                  "name": "nodejs-app",
                  "version": "1.0.0",
                  "description": "Node.js Application",
                  "main": "index.js",
                  "scripts": {
                    "start": "node index.js",
                    "dev": "nodemon index.js"
                  },
                  "dependencies": {
                    "express": "^4.18.2"
                  },
                  "devDependencies": {
                    "nodemon": "^3.0.1"
                  }
                }
                '''))
                
                # Crear app básica de Express
                # Create basic Express app
                (target / "data" / "index.js").write_text(textwrap.dedent('''
                const express = require('express');
                const app = express();
                const port = 3000;

                app.get('/', (req, res) => {
                  res.send('¡Hola desde Node.js! Edita el archivo index.js para personalizar tu aplicación. Nodemon actualizará automáticamente cuando hagas cambios.');
                });

                app.listen(port, '0.0.0.0', () => {
                  console.log(`Aplicación Node.js escuchando en http://0.0.0.0:${port}`);
                  console.log('Nodemon está activo: la aplicación se reiniciará automáticamente cuando se detecten cambios');
                });
                '''))
                
                # Instalar dependencias
                # Install dependencies
                self._run_once_container(
                    "node:18",
                    ["npm", "install"],
                    {str(target / "data"): {"bind": "/app", "mode": "rw"}},
                )
            except Exception as e:
                print(f"Error creating Node.js project: {e}")

        # 4) Escribir docker-compose.yml para Node.js
        # Write docker-compose.yml for Node.js
        compose_text = textwrap.dedent(f"""
        services:
          nodejs:
            image: node:18
            networks:
              - caddy_net
            working_dir: /app
            volumes:
              - "./data:/app"
            command: sh -c "npm install && npm run dev"
            labels:
              caddy: "{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 3000}}}}"
            restart: always
            environment:
              - NODE_ENV=development

          filebrowser:
            image: filebrowser/filebrowser:latest
            networks:
              - caddy_net
            labels:
              caddy: "fb-{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 80}}}}"
            volumes:
              - "./filebrowser_data/filebrowser.db:/database.db"
              - "./data:/srv"
            command: --database /database.db
            restart: always

        networks:
          caddy_net:
            external: true
        """)
        (target / "docker-compose.yml").write_text(compose_text)

        # 5) Levantar servicios con docker compose v2
        subprocess.run(
            ["docker", "compose", "up", "-d"], cwd=target, check=True
        )

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Stack React/Vite con filebrowser
    # React/Vite stack with filebrowser
    def deploy_react_with_filebrowser(
        self, user: str, project: str, zip_path: str | None, admin_pass: str = "admin123"
    ):
        """
        Crea el stack React/Vite con filebrowser en la carpeta del usuario.
        Creates the React/Vite stack with filebrowser in the user's folder.
        """
        target = self._ensure_path(user, project)

        # 0) Descomprimir el zip si se proporciona
        # Extract zip if provided
        if zip_path:
            print(f"Extracting {zip_path} → {target/'data'}")
            with zipfile.ZipFile(zip_path) as zf:
                self._safe_extract(zf, target / "data")
            os.remove(zip_path)  # limpia tmp | Clear tmp
        
        # 1) Inicializar DB para filebrowser
        # Initialize DB for filebrowser
        self._run_once_container(
            "filebrowser/filebrowser",
            ["config", "init", "--database", "/srv/filebrowser.db"],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )

        # 2) Crear usuario admin para filebrowser
        # Create admin user for filebrowser
        self._run_once_container(
            "filebrowser/filebrowser",
            [
                "users",
                "add",
                "admin",
                admin_pass,
                "--database",
                "/srv/filebrowser.db",
                "--perm.admin",
            ],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )
        
        # 3) Crear proyecto React/Vite si no se proporcionó un zip
        # Create React/Vite project if no zip provided
        if not zip_path:
            print(f"Creating React/Vite project in {target/'data'}")
            try:
                # Primero asegurarse que el directorio esté vacío
                # First ensure directory is empty
                if (target / "data").exists() and any((target / "data").iterdir()):
                    shutil.rmtree(target / "data")
                    (target / "data").mkdir(exist_ok=True)
                
                # Ejecutar comandos separados para mejor control y manejo de errores
                # Run separate commands for better control and error handling
                self._run_once_container(
                    "node:18",
                    ["npm", "init", "vite@latest", ".", "--", "--template", "react"],
                    {str(target / "data"): {"bind": "/app", "mode": "rw"}},
                )
                
                # Instalar dependencias después
                # Install dependencies after
                self._run_once_container(
                    "node:18",
                    ["npm", "install"],
                    {str(target / "data"): {"bind": "/app", "mode": "rw"}},
                )
            except Exception as e:
                print(f"Error creating React project: {e}")

        # 4) Escribir docker-compose.yml para React/Vite
        # Write docker-compose.yml for React/Vite
        compose_text = textwrap.dedent(f"""
        services:
          react-vite:
            image: node:18
            networks:
              - caddy_net
            working_dir: /app
            volumes:
              - "./data:/app"
            command: sh -c "npm install && npm run dev -- --host"
            labels:
              caddy: "{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 3000}}}}"
            restart: always

          filebrowser:
            image: filebrowser/filebrowser:latest
            networks:
              - caddy_net
            labels:
              caddy: "fb-{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 80}}}}"
            volumes:
              - "./filebrowser_data/filebrowser.db:/database.db"
              - "./data:/srv"
            command: --database /database.db
            restart: always

        networks:
          caddy_net:
            external: true
        """)
        (target / "docker-compose.yml").write_text(compose_text)

        # 5) Levantar servicios con docker compose v2
        subprocess.run(
            ["docker", "compose", "up", "-d"], cwd=target, check=True
        )
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Stack Next.js con filebrowser
    # Next.js stack with filebrowser
    def deploy_nextjs_with_filebrowser(
        self, user: str, project: str, zip_path: str | None, admin_pass: str = "admin123"
    ):
        """
        Crea el stack Next.js con filebrowser en la carpeta del usuario.
        Creates the Next.js stack with filebrowser in the user's folder.
        """
        target = self._ensure_path(user, project)

        # 0) Descomprimir el zip si se proporciona
        # Extract zip if provided
        if zip_path:
            print(f"Extracting {zip_path} → {target/'data'}")
            with zipfile.ZipFile(zip_path) as zf:
                self._safe_extract(zf, target / "data")
            os.remove(zip_path)  # limpia tmp | Clear tmp
        
        # 1) Inicializar DB para filebrowser
        # Initialize DB for filebrowser
        self._run_once_container(
            "filebrowser/filebrowser",
            ["config", "init", "--database", "/srv/filebrowser.db"],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )

        # 2) Crear usuario admin para filebrowser
        # Create admin user for filebrowser
        self._run_once_container(
            "filebrowser/filebrowser",
            [
                "users",
                "add",
                "admin",
                admin_pass,
                "--database",
                "/srv/filebrowser.db",
                "--perm.admin",
            ],
            {str(target / "filebrowser_data"): {"bind": "/srv", "mode": "rw"}},
        )
        
        # 3) Crear proyecto Next.js si no se proporcionó un zip
        # Create Next.js project if no zip provided
        if not zip_path:
            print(f"Creating Next.js project in {target/'data'}")
            try:
                # Primero asegurarse que el directorio esté vacío
                # First ensure directory is empty
                if (target / "data").exists() and any((target / "data").iterdir()):
                    shutil.rmtree(target / "data")
                    (target / "data").mkdir(exist_ok=True)
                
                # Crear package.json básico para Next.js
                # Create basic package.json for Next.js
                (target / "data" / "package.json").write_text(textwrap.dedent('''
                {
                  "name": "nextjs-app",
                  "version": "0.1.0",
                  "private": true,
                  "scripts": {
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start",
                    "lint": "next lint"
                  },
                  "dependencies": {
                    "next": "14.0.3",
                    "react": "^18.2.0",
                    "react-dom": "^18.2.0"
                  }
                }
                '''))
                
                # Crear estructura básica de carpetas de Next.js
                # Create basic folder structure for Next.js
                (target / "data" / "pages").mkdir(exist_ok=True)
                (target / "data" / "public").mkdir(exist_ok=True)
                (target / "data" / "styles").mkdir(exist_ok=True)
                
                # Crear archivo _app.js básico
                # Create basic _app.js file
                (target / "data" / "pages" / "_app.js").write_text(textwrap.dedent('''
                import '../styles/globals.css'

                function MyApp({ Component, pageProps }) {
                  return <Component {...pageProps} />
                }

                export default MyApp
                '''))
                
                # Crear archivo index.js básico
                # Create basic index.js file
                (target / "data" / "pages" / "index.js").write_text(textwrap.dedent('''
                export default function Home() {
                  return (
                    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
                      <h1>¡Bienvenido a tu aplicación Next.js!</h1>
                      <p>
                        Edita <code>pages/index.js</code> para personalizar esta página.
                        Los cambios se actualizarán automáticamente.
                      </p>
                      <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#f0f0f0', borderRadius: '5px' }}>
                        <h2>Características de Next.js</h2>
                        <ul>
                          <li>Actualización automática en tiempo real</li>
                          <li>Renderizado del lado del servidor (SSR)</li>
                          <li>Generación de sitios estáticos (SSG)</li>
                          <li>Enrutamiento basado en el sistema de archivos</li>
                        </ul>
                      </div>
                    </div>
                  )
                }
                '''))
                
                # Crear archivo globals.css básico
                # Create basic globals.css file
                (target / "data" / "styles" / "globals.css").write_text(textwrap.dedent('''
                html,
                body {
                  padding: 0;
                  margin: 0;
                  font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Oxygen,
                    Ubuntu, Cantarell, Fira Sans, Droid Sans, Helvetica Neue, sans-serif;
                }

                a {
                  color: inherit;
                  text-decoration: none;
                }

                * {
                  box-sizing: border-box;
                }
                '''))
                
                # Crear archivo .gitignore básico
                # Create basic .gitignore file
                (target / "data" / ".gitignore").write_text(textwrap.dedent('''
                # dependencies
                /node_modules
                /.pnp
                .pnp.js

                # testing
                /coverage

                # next.js
                /.next/
                /out/

                # production
                /build

                # misc
                .DS_Store
                *.pem

                # debug
                npm-debug.log*
                yarn-debug.log*
                yarn-error.log*

                # local env files
                .env*.local

                # vercel
                .vercel
                '''))
                
                # Instalar dependencias
                # Install dependencies
                self._run_once_container(
                    "node:18",
                    ["npm", "install"],
                    {str(target / "data"): {"bind": "/app", "mode": "rw"}},
                )
            except Exception as e:
                print(f"Error creating Next.js project: {e}")

        # 4) Escribir docker-compose.yml para Next.js
        # Write docker-compose.yml for Next.js
        compose_text = textwrap.dedent(f"""
        services:
          nextjs:
            image: node:18
            networks:
              - caddy_net
            working_dir: /app
            volumes:
              - "./data:/app"
            command: sh -c "npm install && npm run dev -- --host 0.0.0.0"
            labels:
              caddy: "{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 3000}}}}"
            restart: always
            environment:
              - NODE_ENV=development
              - NEXT_TELEMETRY_DISABLED=1
              - HOSTNAME=0.0.0.0
              - PORT=3000

          filebrowser:
            image: filebrowser/filebrowser:latest
            networks:
              - caddy_net
            labels:
              caddy: "fb-{project}.quiere.cafe"
              caddy.reverse_proxy: "{{{{upstreams 80}}}}"
            volumes:
              - "./filebrowser_data/filebrowser.db:/database.db"
              - "./data:/srv"
            command: --database /database.db
            restart: always

        networks:
          caddy_net:
            external: true
        """)
        (target / "docker-compose.yml").write_text(compose_text)

        # 5) Levantar servicios con docker compose v2
        subprocess.run(
            ["docker", "compose", "up", "-d"], cwd=target, check=True
        )
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # ---------- punto de entrada principal ----------
    # ---------- main entry point ----------
    def handle_request(self, payload: Dict):
        """
        Decide qué hacer según el `Webtype` recibido desde FastAPI.
        Lanza la rutina adecuada.

        Decides what to do according to the `Webtype` received from FastAPI.
        Launches the appropriate routine.
        """
        wtype = payload["Webtype"]
        user = payload["userid"]
        pname = payload["Webname"]

        if wtype == "Estatico":
            self.deploy_static_with_filebrowser(user, pname, payload.get("zip_path"))
        elif wtype == "PHP":
            self.deploy_php_with_filebrowser(user, pname, payload.get("zip_path"))
        elif wtype == "Laravel":
            self.deploy_laravel_with_filebrowser(user, pname, payload.get("zip_path"))
        elif wtype == "React":
            self.deploy_react_with_filebrowser(user, pname, payload.get("zip_path"))
        elif wtype == "Node":
            self.deploy_nodejs_with_filebrowser(user, pname, payload.get("zip_path"))
        elif wtype == "Next":
            self.deploy_nextjs_with_filebrowser(user, pname, payload.get("zip_path"))
        else:
            # Esqueleto para futuros tipos
            # Skeleton for future types
            raise NotImplementedError(f"Webtype {wtype} aún no soportado")

# Helper singleton para no re-crear cliente cada vez
# Helper singleton to avoid re-creating the client each time
docker_manager = DockerManager()
