import os
from pathlib import Path
from django.core.management.base import BaseCommand
from openpyxl import load_workbook
from inventario.models import Equipo


def limpiar(v):
    if v is None:
        return ''
    return str(v).strip()


class Command(BaseCommand):
    help = 'Importa equipos desde los archivos Excel'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Re-importar incluso si ya hay datos')

    def handle(self, *args, **options):
        data_dir = Path(__file__).resolve().parent.parent.parent.parent / 'data'

        if Equipo.objects.exists() and not options['force']:
            self.stdout.write(f'Ya hay {Equipo.objects.count()} equipos. Usa --force para re-importar.')
            return

        Equipo.objects.all().delete()

        self._importar_rx(str(data_dir / 'Estado de los RX Provincia x marca .xlsx'))
        self._importar_usd_marcas(str(data_dir / 'Estado de los USD x Marcas.xlsx'))
        self._importar_usd_municipios(str(data_dir / 'Estado de los USD x Municipios.xlsx'))
        self._importar_plan_mtto(str(data_dir / 'Plan de Mtto.xlsx'))

        total = Equipo.objects.count()
        self.stdout.write(self.style.SUCCESS(f'{total} equipos importados.'))

    def _importar_rx(self, path):
        wb = load_workbook(path)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row[0]:
                    continue
                Equipo.objects.create(
                    municipio=limpiar(row[0]),
                    tipo='RX',
                    unidad_salud=limpiar(row[2]),
                    denominacion=limpiar(row[3]),
                    marca=limpiar(row[4]),
                    modelo=limpiar(row[5]),
                    numero_serie=limpiar(row[6]),
                    observaciones=limpiar(row[7]),
                    estado=limpiar(row[8]),
                    fuente='Estado de los RX Provincia x marca',
                )
        self.stdout.write(f'  RX: {wb.sheetnames}')

    def _importar_usd_marcas(self, path):
        wb = load_workbook(path)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row[0]:
                    continue
                Equipo.objects.create(
                    municipio=limpiar(row[0]),
                    tipo='USD',
                    unidad_salud=limpiar(row[1]),
                    marca=limpiar(row[2]),
                    modelo=limpiar(row[3]),
                    numero_serie=limpiar(row[4]),
                    observaciones=limpiar(row[5]),
                    estado=limpiar(row[6]),
                    fuente='Estado de los USD x Marcas',
                )
        self.stdout.write(f'  USD Marcas: {wb.sheetnames}')

    def _importar_usd_municipios(self, path):
        wb = load_workbook(path)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row[0]:
                    continue
                Equipo.objects.create(
                    municipio=limpiar(row[0]),
                    tipo='USD',
                    unidad_salud=limpiar(row[1]),
                    local=limpiar(row[2]),
                    servicio=limpiar(row[3]),
                    marca=limpiar(row[4]),
                    modelo=limpiar(row[5]),
                    numero_serie=limpiar(row[6]),
                    observaciones=limpiar(row[7]),
                    estado=limpiar(row[8]),
                    fuente='Estado de los USD x Municipios',
                )
        self.stdout.write(f'  USD Municipios: {wb.sheetnames}')

    def _importar_plan_mtto(self, path):
        wb = load_workbook(path)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            Equipo.objects.create(
                tipo='OTRO',
                unidad_salud=limpiar(row[0]),
                denominacion=limpiar(row[1]),
                marca=limpiar(row[2]),
                modelo=limpiar(row[3]),
                numero_serie=limpiar(row[4]),
                estado=limpiar(row[5]),
                frecuencia=limpiar(row[6]),
                fuente='Plan de Mtto',
            )
        self.stdout.write('  Plan de Mtto')
