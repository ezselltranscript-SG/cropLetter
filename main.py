from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import StreamingResponse
from PIL import Image
import io
import zipfile
from typing import Optional
import os

app = FastAPI(title="Image Cropping Service", version="1.0.0")

@app.post("/crop-image/")
async def crop_image(
    file: UploadFile = File(...),
    split_point: Optional[int] = Form(None),
    split_percentage: Optional[float] = Form(None)
):
    """
    Divide una imagen en dos partes: header (arriba) y body (abajo)
    
    Parámetros:
    - file: Imagen PNG o JPG
    - split_point: Punto de división en píxeles desde arriba (opcional)
    - split_percentage: Punto de división como porcentaje de la altura (0.0-1.0, opcional)
    
    Si no se especifica ningún punto, se divide por la mitad (50%)
    """
    
    # Validar tipo de archivo
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    
    if file.content_type not in ['image/png', 'image/jpeg', 'image/jpg']:
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PNG y JPG")
    
    try:
        # Leer la imagen
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # Obtener dimensiones
        width, height = image.size
        
        # Determinar punto de división
        if split_point is not None:
            if split_point < 0 or split_point >= height:
                raise HTTPException(
                    status_code=400, 
                    detail=f"El punto de división debe estar entre 0 y {height-1} píxeles"
                )
            division_y = split_point
        elif split_percentage is not None:
            if split_percentage < 0.0 or split_percentage > 1.0:
                raise HTTPException(
                    status_code=400, 
                    detail="El porcentaje debe estar entre 0.0 y 1.0"
                )
            division_y = int(height * split_percentage)
        else:
            # Por defecto, dividir por la mitad
            division_y = height // 2
        
        # Verificar que la división sea válida
        if division_y <= 0 or division_y >= height:
            raise HTTPException(
                status_code=400, 
                detail="El punto de división no permite crear dos imágenes válidas"
            )
        
        # Crear las dos partes
        # Header: desde arriba hasta el punto de división
        image_header = image.crop((0, 0, width, division_y))
        
        # Body: desde el punto de división hasta abajo
        image_body = image.crop((0, division_y, width, height))
        
        # Crear ZIP en memoria
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Guardar image_header
            header_buffer = io.BytesIO()
            # Mantener el formato original
            format_name = 'PNG' if file.content_type == 'image/png' else 'JPEG'
            image_header.save(header_buffer, format=format_name)
            zip_file.writestr("image_header." + format_name.lower(), header_buffer.getvalue())
            
            # Guardar image_body
            body_buffer = io.BytesIO()
            image_body.save(body_buffer, format=format_name)
            zip_file.writestr("image_body." + format_name.lower(), body_buffer.getvalue())
        
        zip_buffer.seek(0)
        
        # Crear nombre del archivo ZIP
        original_name = os.path.splitext(file.filename)[0] if file.filename else "image"
        zip_filename = f"{original_name}_cropped.zip"
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando la imagen: {str(e)}")

@app.get("/")
async def root():
    return {
        "message": "Image Cropping Service",
        "endpoints": {
            "POST /crop-image/": "Divide una imagen en header y body",
        },
        "parameters": {
            "file": "Imagen PNG o JPG (requerido)",
            "split_point": "Punto de división en píxeles desde arriba (opcional)",
            "split_percentage": "Punto de división como porcentaje 0.0-1.0 (opcional)"
        },
        "examples": {
            "split_by_pixels": "split_point=300 (divide a 300px desde arriba)",
            "split_by_percentage": "split_percentage=0.3 (divide al 30% de la altura)",
            "default": "Sin parámetros = divide por la mitad"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "OK"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)