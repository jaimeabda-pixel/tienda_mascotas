from django.http import HttpResponse

def saludo(request):
    return HttpResponse("hola esta es mi primera pagina")


def despedida(request):
    return HttpResponse("chao jaime hermoso inteligente y millonario")