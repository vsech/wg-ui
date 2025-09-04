"""
QR code generation service
"""
import qrcode
import io
import base64


class QRCodeService:
    """QR code generation service"""

    @staticmethod
    def generate_qr_code(config_content: str) -> str:
        """Generate QR code for WireGuard configuration"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(config_content)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"
